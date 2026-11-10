"""Demo actors and real catalog selection; bibliographic writes use the importer."""
from dataclasses import dataclass
import uuid

from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.auth.models import AuthAccount
from app.modules.books.models import CatalogSource, Edition, Work
from app.modules.demo.models import DemoMode
from app.modules.users.identity_models import Profile, ProfileCapability
from app.modules.users.models import User

NAMESPACE = uuid.UUID('cf7e9d28-6cf2-4e90-b41c-995ec038f7ad')
PERSONAS = (
    ('camila', 'Camila Torres · Demo', 'lector'),
    ('diego', 'Diego Rojas · Demo', 'lector'),
    ('valentina', 'Valentina Soto · Demo', 'lector'),
    ('matias', 'Matías Silva · Demo', 'lector'),
    ('isabel', 'Isabel Fuentes · Demo', 'lector'),
    ('autor', 'Javier Medina · Demo', 'autor'),
    ('influencer', 'Paula Recomienda · Demo', 'influencer'),
    ('libreria', 'Librería Entre Páginas · Demo', 'libreria'),
)


def identifier(key):
    return uuid.uuid5(NAMESPACE, key)


class DemoPaused(Exception):
    pass


def ensure_enabled():
    if not get_settings().catalog_discovery_enabled:
        raise ValueError('El modo demo requiere CATALOG_DISCOVERY_ENABLED=true')
    with SessionLocal() as db:
        mode = db.get(DemoMode, 1)
        if mode is None or not mode.enabled:
            raise DemoPaused()


def prepare_actors():
    password = get_settings().libria_demo_password
    if len(password) < 8:
        raise ValueError('Falta configurar LIBRIA_DEMO_PASSWORD')
    with SessionLocal.begin() as db:
        for key, name, role in PERSONAS:
            user_id = identifier('user:' + key)
            email = f'showcase.{key}@example.com'
            account = db.scalar(select(AuthAccount).where(AuthAccount.email == email))
            user = db.get(User, user_id)
            if account and account.user_id != user_id:
                raise ValueError('Un correo demo pertenece a otra identidad; no se modifica')
            if user is None:
                user = User(id=user_id, display_name=name, role=role,
                            biography='Perfil ficticio para demostraciones de LibrIAverse.')
                user.auth_account = AuthAccount(email=email, password_hash=hash_password(password))
                db.add(user)
                db.flush()
                profile = Profile(id=identifier('profile:' + key), kind='personal',
                                  owner_user_id=user_id, display_name=name)
                db.add(profile)
                db.flush()
                for capability in ({'lector', role} if role in {'autor', 'influencer'} else {'lector'}):
                    db.add(ProfileCapability(profile_id=profile.id, capability=capability))
            elif account is None or user.account_status != 'active' or user.suspended_at is not None:
                raise ValueError('Una cuenta demo fue deshabilitada o modificada; revisa sus permisos')
            # Existing accounts/passwords are preserved. No real account is reset.


@dataclass(frozen=True)
class DemoBook:
    work_id: str
    edition_id: str
    title: str
    pages: int | None

    def library_payload(self):
        return {'book_ref': self.work_id, 'book_title': self.title[:200], 'edition_id': self.edition_id}


def catalog_books(edition_ids=None):
    with SessionLocal() as db:
        query = select(Work.id, Edition.id, Edition.title, Edition.page_count)
        query = query.join(Edition, Edition.work_id == Work.id).where(Edition.language == 'es',
            select(CatalogSource.id).where(CatalogSource.edition_id == Edition.id,
                CatalogSource.provider.in_(('google-books', 'open-library')),
                CatalogSource.validation_status == 'validated').exists())
        if edition_ids:
            query = query.where(Edition.id.in_([uuid.UUID(value) for value in edition_ids]))
        rows = db.execute(query
            .order_by(Edition.cover_url.is_(None), Work.id, Edition.id).limit(100)).all()
    if edition_ids:
        by_id = {str(edition): DemoBook(str(work), str(edition), title, pages)
                 for work, edition, title, pages in rows}
        if any(value not in by_id for value in edition_ids):
            raise ValueError('Una edición seleccionada para la demo ya no está disponible')
        return [by_id[value] for value in edition_ids]
    books = {}
    for work, edition, title, pages in rows:
        books.setdefault(str(work), DemoBook(str(work), str(edition), title, pages))
    return list(books.values())[:12]


def post_reference(edition_id):
    with SessionLocal() as db:
        reference = db.scalar(select(CatalogSource.external_id).where(
            CatalogSource.edition_id == uuid.UUID(edition_id),
            CatalogSource.provider == 'libria-feed').order_by(CatalogSource.external_id).limit(1))
        if reference is None:
            raise ValueError('La edición requiere una referencia interna de catálogo')
        return reference


def mark_demo_result(path, result):
    """Keep simulated evidence out of real analytics using existing provenance."""
    if not isinstance(result, dict):
        return
    entities = []
    if path == '/posts':
        entities.append(('post', result['id']))
    elif path == '/reviews':
        entities.append(('review', result['id']))
    elif path in ('/readings/library', '/readings/events'):
        entities.append(('lecturas', result['reading_id']))
        if result.get('event_id'):
            entities.append(('event', result['event_id']))
    elif path.endswith('/comments') and result.get('comment'):
        entities.append(('comentarios_publicacion', result['comment']['id']))
    with SessionLocal.begin() as db:
        for kind, entity in entities:
            db.execute(text('INSERT INTO app.procedencia_demo (entity_type,entity_id,dataset_version) '
                            'VALUES (:kind,:id,:version) ON CONFLICT DO NOTHING'),
                       {'kind': kind, 'id': uuid.UUID(str(entity)), 'version': 'showcase-v1'})


def prepare_catalog(admin_id, *, require_active=True, refresh=False):
    from app.modules.demo.selection import prepare_selection, valid_selection
    from app.modules.users.identity_models import AccountPermission
    def check_active():
        if require_active:
            ensure_enabled()
        else:
            with SessionLocal() as db:
                if db.get(AccountPermission, (admin_id, 'admin')) is None:
                    raise PermissionError('Se requiere el administrador que autorizó la demo')
    with SessionLocal() as db:
        selected = db.get(DemoMode, 1).catalog_edition_ids
    if not refresh and valid_selection(selected):
        return catalog_books(selected)
    check_active()
    edition_ids, _ = prepare_selection(admin_id, check_active)
    books = catalog_books(edition_ids)
    return remember_catalog(books, check_active=check_active)


def remember_catalog(books, *, check_active=ensure_enabled):
    check_active()
    with SessionLocal.begin() as db:
        mode = db.get(DemoMode, 1)
        ids = [book.edition_id for book in books]
        if mode.catalog_edition_ids != ids:
            # Continue at an unused action key and a complete reading cycle.
            # Existing activities are preserved rather than rewritten/deleted.
            mode.sequence = ((mode.sequence + 15) // 16) * 16
            mode.last_run_at = None
            mode.last_error = None
        mode.catalog_edition_ids = ids
    return books
