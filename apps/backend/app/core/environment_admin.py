"""Administrator-only editing of the two fixed application environment files."""
import hashlib
import io
import os
from pathlib import Path
import re
import tempfile
from threading import Lock
from typing import Annotated, Literal

from dotenv import dotenv_values, set_key
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import Settings
from app.modules.users.roles_router import get_admin

router = APIRouter(prefix='/admin/environment', tags=['environment-administration'], dependencies=[Depends(get_admin)])
APPS = Path(__file__).resolve().parents[3]
LOCK = Lock()
WEB_KEYS = {'VITE_API_URL', 'VITE_GOOGLE_BOOKS_API_KEY'}


def env_path(target):
    return APPS / target / '.env'


def secret(key):
    return bool(re.search(r'SECRET|PASSWORD|TOKEN|API_KEY|DATABASE_URL|SMTP_USERNAME', key))


def snapshot(target):
    path = env_path(target)
    raw = path.read_bytes() if path.exists() else b''
    values = dotenv_values(stream=io.StringIO(raw.decode('utf-8-sig')), interpolate=False)
    keys = {name.upper() for name in Settings.model_fields} if target == 'backend' else WEB_KEYS
    fields = []
    for key in sorted(keys):
        value = values.get(key)
        fields.append(dict(key=key, value=None if secret(key) else value,
                           secret=secret(key), configured=value is not None and value != ''))
    return dict(revision=hashlib.sha256(raw).hexdigest(), fields=fields)


class Update(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: str
    values: dict[str, str] = Field(max_length=200)


@router.get('/{target}')
def read_environment(target: Literal['backend', 'web'], response: Response):
    response.headers['Cache-Control'] = 'no-store'
    with LOCK:
        return snapshot(target)


def save_environment(target, data):
    with LOCK:
        current = snapshot(target)
        if current['revision'] != data.revision:
            raise HTTPException(409, 'Otro administrador modificó este archivo. Recarga antes de guardar.')
        allowed = {field['key'] for field in current['fields']}
        if not data.values.keys() <= allowed:
            raise HTTPException(422, 'Hay variables no admitidas.')
        if any('\n' in value or '\r' in value or '\x00' in value or len(value) > 16000 for value in data.values.values()):
            raise HTTPException(422, 'Los valores deben ocupar una sola línea y no superar 16000 caracteres.')
        path = env_path(target)
        previous = dotenv_values(path, interpolate=False) if path.exists() else {}
        merged = {**previous, **data.values}
        if target == 'backend':
            try:
                Settings(_env_file=None, **{key.lower(): value for key, value in merged.items() if key in allowed and value is not None})
            except ValidationError as error:
                names = sorted({str(item['loc'][0]).upper() if item['loc'] else 'CONFIGURACIÓN DEL CATÁLOGO' for item in error.errors()})
                raise HTTPException(422, 'Configuración inválida. Revisa: ' + ', '.join(names)) from None
        elif 'VITE_API_URL' in data.values:
            from urllib.parse import urlparse
            url = urlparse(data.values['VITE_API_URL'])
            if url.scheme not in ('http', 'https') or not url.netloc or url.username or url.password:
                raise HTTPException(422, 'VITE_API_URL debe ser una URL HTTP o HTTPS sin credenciales.')
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.environment-', suffix='.tmp')
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(path.read_bytes() if path.exists() else b'')
            for key, value in data.values.items():
                set_key(temporary, key, value, quote_mode='always')
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return snapshot(target)


@router.patch('/{target}')
def update_environment(target: Literal['backend', 'web'], data: Update, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    try:
        return save_environment(target, data)
    except OSError:
        raise HTTPException(503, 'No se pudo guardar el archivo de configuración. Revisa los permisos del servidor.') from None
