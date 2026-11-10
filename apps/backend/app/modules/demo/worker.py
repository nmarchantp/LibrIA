"""One cluster-wide producer; all social activity goes through the current API."""
import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import logging
import uuid

import httpx
from sqlalchemy import text, update
from sqlalchemy.exc import ProgrammingError

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.modules.demo.models import DemoMode
from app.modules.demo.service import (
    DemoPaused, NAMESPACE, PERSONAS, ensure_enabled, identifier, prepare_actors, prepare_catalog, mark_demo_result,
)

logger = logging.getLogger(__name__)
LOCK_ID = 963470087


@contextmanager
def producer_lease():
    # Session lock spans API requests; independent of their catalog transactions.
    with engine.connect() as connection:
        locked = connection.execute(text('SELECT pg_try_advisory_lock(:key)'), {'key': LOCK_ID}).scalar()
        connection.commit()
        try:
            yield locked
        finally:
            if locked:
                connection.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': LOCK_ID})
                connection.commit()


class DemoAPI:
    def __init__(self, client):
        self.client = client
        self.tokens = {}

    async def request(self, actor, method, path, payload=None, *, sequence=0):
        ensure_enabled()
        for attempt in range(2):
            if actor not in self.tokens:
                result = await self.client.post(get_settings().api_prefix + '/auth/login', json={
                    'email': f'showcase.{actor}@example.com', 'password': get_settings().libria_demo_password})
                if result.status_code != 200:
                    raise RuntimeError(f'No se pudo iniciar la cuenta demo {actor} (HTTP {result.status_code}).')
                self.tokens[actor] = result.json()['access_token']
            headers = {'Authorization': 'Bearer ' + self.tokens[actor]}
            if method != 'GET':
                headers['Idempotency-Key'] = str(uuid.uuid5(NAMESPACE, f'activity-v2:{sequence}:{actor}:{method}:{path}'))
            ensure_enabled()
            response = await self.client.request(method, get_settings().api_prefix + path,
                                                 json=payload, headers=headers)
            if response.status_code == 401 and attempt == 0:
                self.tokens.pop(actor, None)
                continue
            if response.is_error:
                # Do not persist payloads, URLs containing secrets, or provider responses.
                raise RuntimeError(f'La acción demo {method} {path.split("?")[0]} falló (HTTP {response.status_code}).')
            result = response.json() if response.status_code != 204 else None
            if method != 'GET':
                await asyncio.to_thread(mark_demo_result, path, result)
            return result


def event_payload(book, sequence):
    start = datetime.now(timezone.utc) + timedelta(days=3 + sequence % 10)
    return {
        'source': 'event', 'kind': 'community', 'publication_type': 'event',
        'title': 'Club de lectura: conversemos sobre ' + book.title[:100],
        'body': 'Un encuentro para compartir interpretaciones, descubrir autores y elegir nuestra próxima lectura.',
        'work_id': book.work_id, 'edition_id': book.edition_id,
        'event_details': {
            'start_date': start.date().isoformat(), 'start_time': '18:00',
            'end_date': start.date().isoformat(), 'end_time': '19:30',
            'timezone': 'America/Santiago', 'location': 'Encuentro virtual de demostración',
            'organizer': 'Comunidad LibrIAverse · Demo', 'category': 'book_club',
        },
    }


async def review_action(api, actor, book, sequence):
    import random
    rng = random.Random(f'showcase-review:{sequence}:{actor}:{book.work_id}')
    existing = await api.request(actor, 'GET', '/reviews/me?work_id=' + book.work_id)
    # Keep an existing review and its history; never repeatedly edit the same text.
    if existing:
        return
    bodies = (
        'Una lectura que me dejó pensando en sus personajes. La recomendaría para conversar en un club de lectura.',
        'Disfruté el ritmo y la forma de construir la historia. Me quedo con varias ideas para una segunda lectura.',
        'Lo mejor fue descubrir cómo se conectan sus temas. Hay momentos que invitan a detenerse y reflexionar.',
        'Me gustó su propuesta y el desarrollo de los personajes. Una buena opción para salir de la rutina lectora.',
    )
    await api.request(actor, 'POST', '/reviews', {
        'work_id': book.work_id, 'edition_id': book.edition_id,
        'author_profile_id': str(identifier('profile:' + actor)),
        'body': rng.choice(bodies), 'rating': rng.choice([4, 4.25, 4.5, 4.75, 5]),
        'status': 'published',
    }, sequence=sequence)


def shuffled_schedule(sequence):
    """Balanced randomness: every block contains all publication categories."""
    import random
    block, position = divmod(sequence, 32)
    actions = ['reading'] * 20 + ['note', 'theory', 'free', 'event', 'promotion', 'news', 'launch',
                                 'follow', 'social_interaction', 'review_interaction',
                                 'progress_interaction', 'event_interaction']
    random.Random(f'showcase-v2-block:{block}').shuffle(actions)
    reading_index = block * 20 + actions[:position].count('reading')
    return actions[position], reading_index


def reading_actor(index):
    import random
    readers = [p[0] for p in PERSONAS if p[2] != 'libreria']
    round_number, position = divmod(index, len(readers))
    random.Random(f'showcase-v2-readers:{round_number}').shuffle(readers)
    if round_number:
        previous = [p[0] for p in PERSONAS if p[2] != 'libreria']
        random.Random(f'showcase-v2-readers:{round_number - 1}').shuffle(previous)
        if readers[0] == previous[-1]:
            readers[0], readers[1] = readers[1], readers[0]
    return readers[position]


def choose_reading(books, states, actor):
    import random
    # Keep each person's active attempt. Never advance a random unrelated book.
    by_work = {book.work_id: book for book in books}
    selected_states = [state for state in states if state['work_id'] in by_work]
    active = next((s for s in selected_states if s['status'] == 'reading'), None)
    if active:
        return by_work[active['work_id']], active
    pending = next((s for s in selected_states if s['status'] == 'pending'), None)
    if pending:
        return by_work[pending['work_id']], pending
    ordered = list(books)
    random.Random('showcase-v2-book-assignment').shuffle(ordered)
    readers = [p[0] for p in PERSONAS if p[2] != 'libreria']
    offset = readers.index(actor) % len(ordered)
    ordered = ordered[offset:] + ordered[:offset]
    completed = {s['work_id'] for s in selected_states if s['status'] == 'finished'}
    available = [book for book in ordered if book.work_id not in completed]
    # Once the whole selection is read, another attempt is a legitimate reread.
    book = available[0] if available else ordered[len(selected_states) % len(ordered)]
    return book, next((s for s in selected_states if s['work_id'] == book.work_id), None)


async def independent_reading(api, books, actor, sequence, rng):
    states = await api.request(actor, 'GET', '/readings/me')
    book, state = choose_reading(books, states, actor)
    if state is None:
        state = await api.request(actor, 'POST', '/readings/library', book.library_payload(), sequence=sequence)
    payload = book.library_payload()
    if state['status'] != 'reading':
        # Recover a review if a previous finish succeeded but its review request
        # was interrupted. Existing reviews are preserved by review_action.
        finished = next((s for s in states if s['status'] == 'finished' and
                         any(b.work_id == s['work_id'] for b in books)), None)
        if finished:
            previous_book = next(b for b in books if b.work_id == finished['work_id'])
            await review_action(api, actor, previous_book, sequence)
        return await api.request(actor, 'POST', '/readings/events',
            {**payload, 'event': 'start', 'page_count': book.pages}, sequence=sequence)
    page = state['current_page']
    total = state.get('total_pages')
    finish_at = (total * rng.uniform(.55, .85)) if total else rng.randint(70, 160)
    if (total is not None and total <= 1) or (page > 0 and (page >= finish_at or (total is not None and page >= total - 1))):
        result = await api.request(actor, 'POST', '/readings/events', {**payload, 'event': 'finish',
            'reading_id': state['reading_id'], 'reflection': {'sentiment': rng.choice(['positivo', 'mixto']),
                'aspects': rng.sample(['personajes', 'historia', 'estilo', 'ritmo'], 2),
                'emotions': [rng.choice(['asombro', 'esperanza', 'nostalgia', 'tension'])],
                'reflection': rng.choice(['Me quedo pensando en las decisiones de sus personajes.',
                    'Disfrut? descubrir c?mo se conectan los temas a lo largo de la historia.',
                    'Una lectura con momentos que dan ganas de comentar en comunidad.'])}}, sequence=sequence)
        await review_action(api, actor, book, sequence)
        return result
    increment = max(1, round(total * rng.uniform(.18, .43))) if total else rng.randint(20, 55)
    next_page = min(total - 1, page + increment) if total else page + increment
    if next_page <= page:
        return
    return await api.request(actor, 'POST', '/readings/events', {**payload, 'event': 'progress',
        'reading_id': state['reading_id'], 'current_page': next_page}, sequence=sequence)


PUBLICATION_TEXTS = {
    'note': ['Anot? una pregunta para mi pr?xima conversaci?n: ?qu? personaje cambia m?s a lo largo de la historia?',
             'Hay peque?os detalles que cobran otro sentido al seguir leyendo. Los estoy guardando en mi cuaderno.',
             'Pausa de lectura para anotar una escena que me dej? pensando en las decisiones de sus personajes.'],
    'theory': ['Mi teor?a: algunos detalles del inicio anticipan las decisiones m?s importantes de los personajes.',
               'Creo que hay una conexi?n entre el conflicto principal y la forma en que se presenta el mundo de esta historia.',
               'Estoy reuniendo pistas para una teor?a sobre los personajes. Quiero ver si se sostiene al terminar.'],
    'free': ['?Qu? est?n leyendo esta semana? Me gusta descubrir recomendaciones fuera de mis g?neros habituales.',
             'Hoy cambi? mi rutina por una tarde de lectura. ?Prefieren leer con m?sica o en silencio?',
             'Busco mi pr?xima lectura compartida: ?qu? historia les dej? ganas de conversar al terminar?'],
    'promotion': ['Selecci?n de la semana: historias para descubrir y compartir. Promoci?n de demostraci?n.',
                  'Nuestra mesa de recomendaciones se renueva con propuestas para distintos gustos lectores. Selecci?n demo.',
                  'Una invitaci?n para explorar otro g?nero en la pr?xima visita a la librer?a. Propuesta de demostraci?n.'],
    'news': ['Estamos preparando nuestra pr?xima selecci?n compartida. ?Qu? g?nero les gustar?a explorar?',
             'Esta semana abrimos una conversaci?n sobre historias que nos sorprenden. Sus recomendaciones son bienvenidas.',
             'Ya tenemos una nueva propuesta para nuestro rinc?n de lecturas. Nos encantar? escuchar sus opiniones.'],
    'launch': ['Presentamos una nueva conversaci?n de nuestro ciclo de lecturas: historias para imaginar y debatir.',
               'Se suma una propuesta a nuestro recorrido lector. ?Qui?n se anima a descubrirla en comunidad?',
               'Abrimos un nuevo espacio para conversar sobre esta historia y compartir distintas miradas.'],
}


async def generate_action(api, books, sequence):
    """Interleave independent readers, varied books, posts and conversations."""
    import random
    rng = random.Random(f'showcase-v2-action:{sequence}')
    action, reading_index = shuffled_schedule(sequence)
    readers = [p[0] for p in PERSONAS if p[2] != 'libreria']
    if action == 'reading':
        return await independent_reading(api, books, reading_actor(reading_index), sequence, rng)
    book = rng.choice(books)
    actor = rng.choice(readers)
    if action in (*PUBLICATION_TEXTS, 'event'):
        author = actor if action in ('note', 'theory') else rng.choice(['influencer', 'autor']) if action == 'free' else 'libreria' if action in ('promotion', 'news') else 'autor'
        if action == 'event':
            payload = event_payload(book, sequence)
            payload['body'] = rng.choice(['Un encuentro para compartir interpretaciones y elegir nuestra pr?xima lectura.',
                'Trae tus preguntas y recomendaciones: conversaremos sobre esta historia en comunidad.',
                'Nos reunimos para descubrir diferentes miradas de una misma lectura.'])
        else:
            payload = {'source': 'community', 'kind': 'community', 'publication_type': action,
                'title': book.title[:160] if action != 'free' else rng.choice(['Lecturas de la semana', 'Una pausa entre libros', 'Recomendaciones para compartir']),
                'body': rng.choice(PUBLICATION_TEXTS[action]), 'work_id': book.work_id, 'edition_id': book.edition_id}
            if action in ('note', 'theory'):
                from app.modules.demo.service import post_reference
                payload.update(book_ref=post_reference(book.edition_id), book_title=book.title[:200])
        payload['author_profile_id'] = str(identifier('profile:' + author))
        return await api.request(author, 'POST', '/posts', payload, sequence=sequence)
    if action == 'follow':
        other = rng.choice([reader for reader in readers if reader != actor])
        return await api.request(other, 'POST', f'/profiles/{identifier("profile:" + actor)}/follow', sequence=sequence)
    category = {'social_interaction': 'social', 'review_interaction': 'reviews',
                'progress_interaction': 'progress', 'event_interaction': 'events'}[action]
    page = await api.request(actor, 'GET', '/mural/' + category + '?limit=10')
    demo_users = {str(identifier('user:' + p[0])) for p in PERSONAS}
    candidates = [item for item in page['items'] if str(item['user_id']) in demo_users and
                  str(item['user_id']) != str(identifier('user:' + actor))]
    if candidates:
        item = rng.choice(candidates)
        target = f'/activities/{item["feed_item_type"]}/{item["id"]}'
        await api.request(actor, 'PUT', target + '/like', sequence=sequence)
        await api.request(actor, 'PUT', target + '/view', {'action': 'open_comments'}, sequence=sequence)
        await api.request(actor, 'POST', target + '/comments', {'body': rng.choice([
            '?Gracias por compartir! Me lo llevo a mi lista de pr?ximas lecturas.',
            'Me gustar?a conversar sobre esta lectura en el pr?ximo encuentro.',
            'Qu? interesante ver otras experiencias de lectura.',
            'Me dio curiosidad tu recomendaci?n. ?Qu? fue lo que m?s te gust??'])}, sequence=sequence)
        if category == 'events':
            await api.request(actor, 'PUT', f'/events/{item["id"]}/attendance', sequence=sequence)


def due_state():
    with SessionLocal() as db:
        state = db.get(DemoMode, 1)
        if state is None or not state.enabled:
            return None
        # Prepare a useful initial mural quickly, then settle into the chosen pace.
        interval = 2 if state.sequence < 32 else state.interval_seconds
        if state.last_error:
            interval = max(interval, 60)
        if state.last_run_at and (datetime.now(timezone.utc) - state.last_run_at).total_seconds() < interval:
            return None
        return state


def record_result(sequence, error=None):
    with SessionLocal.begin() as db:
        values = {'last_run_at': datetime.now(timezone.utc), 'last_error': error}
        if error is None:
            values['sequence'] = sequence + 1
        db.execute(update(DemoMode).where(DemoMode.id == 1, DemoMode.sequence == sequence).values(**values))


async def run_worker(app):
    prepared = False
    books = None
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://demo.internal') as client:
        api = DemoAPI(client)
        while True:
            try:
                with producer_lease() as acquired:
                    state = due_state() if acquired else None
                    if state:
                        try:
                            if not prepared:
                                await complete_blocking(prepare_actors)
                                prepared = True
                            if books is None or [b.edition_id for b in books] != state.catalog_edition_ids:
                                books = await complete_blocking(prepare_catalog, state.updated_by)
                                state = due_state()
                                if state is None:
                                    continue
                            await generate_action(api, books, state.sequence)
                            record_result(state.sequence)
                        except DemoPaused:
                            pass
                        except Exception as error:
                            logger.exception('Demo activity failed at step %s', state.sequence)
                            message = str(error) if isinstance(error, (RuntimeError, ValueError)) else 'No se pudo completar la actividad. Revisa los registros del backend y el acceso al catálogo.'
                            record_result(state.sequence, message[:300])
            except ProgrammingError:
                # API remains available before the explicitly authorized migration.
                await asyncio.sleep(30)
            except Exception:
                logger.exception('Demo worker could not read its state')
                await asyncio.sleep(30)
            await asyncio.sleep(2)


async def complete_blocking(function, *args):
    # Cancellation must not release the producer lock while an import thread
    # is still writing; wait for that bounded operation before shutting down.
    operation = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(operation)
    except asyncio.CancelledError:
        try:
            await operation
        finally:
            raise
