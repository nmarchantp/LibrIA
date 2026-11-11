"""Compatibility CLI for the shared administrator-controlled demo producer."""
import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import get_settings


def request(base, path, payload=None, token=None, method=None):
    headers = {'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    req = Request(base.rstrip('/') + path, headers=headers, method=method,
                  data=json.dumps(payload).encode() if payload is not None else None)
    with urlopen(req, timeout=20) as response:
        return json.loads(response.read())


def main():
    parser = argparse.ArgumentParser(description='Controla el modo demo compartido; no inicia un segundo generador.')
    parser.add_argument('--api-url', default='http://127.0.0.1:8000/api')
    parser.add_argument('--interval', type=int, default=30)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--enable', action='store_true')
    modes.add_argument('--disable', action='store_true')
    args = parser.parse_args()
    if not 10 <= args.interval <= 3600:
        parser.error('--interval debe estar entre 10 y 3600 segundos')
    try:
        token = request(args.api_url, '/auth/login', {'email': 'demo.admin@example.com',
            'password': get_settings().libria_demo_admin_password or get_settings().libria_demo_password})['access_token']
        if args.enable or args.disable:
            state = request(args.api_url, '/admin/demo', {'enabled': args.enable,
                'interval_seconds': args.interval}, token, 'PATCH')
        else:
            state = request(args.api_url, '/admin/demo', token=token)
        print(json.dumps(state, ensure_ascii=False))
        print('Control disponible también en Administración > Configuración > Modo demostración.')
    except HTTPError as error:
        raise SystemExit(f'No se pudo controlar la demo (HTTP {error.code}). Usa una cuenta administradora y aplica la migración 0087.') from None
    except (URLError, TimeoutError, OSError):
        raise SystemExit('No se pudo conectar con la API. Inicia el backend antes de activar la demo.') from None


if __name__ == '__main__':
    main()
