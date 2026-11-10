"""Complete fictional publications using the verified catalog and original covers."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.modules.demo.covers import cover_path, valid_image
from app.modules.demo.service import post_reference


EVENTS = (
    ('book_club', 'Club de lectura', 'Sala virtual de Entre Páginas · Demo', '18:00', '19:30', 0),
    ('workshop', 'Taller de escritura y lectura', 'Sala de talleres Entre Páginas · Demo', '16:00', '18:00', 0),
    ('fair', 'Feria de intercambio de libros', 'Patio cultural Entre Páginas · Demo', '11:00', '19:00', 1),
    ('meetup', 'Encuentro de lectores', 'Café literario Entre Páginas · Demo', '17:00', '18:30', 0),
    ('other', 'Lectura en voz alta', 'Sala virtual de Entre Páginas · Demo', '19:00', '20:00', 0),
)


def event_payload(book, sequence):
    category, title, location, start_time, end_time, days = EVENTS[(sequence // 32) % len(EVENTS)]
    start = datetime.now(ZoneInfo('America/Santiago')).date() + timedelta(days=3 + sequence % 10)
    return {
        'source': 'event', 'kind': 'community', 'publication_type': 'event',
        'title': f'{title}: {book.title}'[:200],
        'body': (f'Nos reunimos alrededor de **{book.title[:120]}**. Trae una pregunta, '
                 'un pasaje favorito o simplemente ganas de escuchar. No hace falta haber terminado el libro. '
                 'Confirma tu asistencia aquí. Actividad ficticia de demostración.'),
        'work_id': book.work_id, 'edition_id': book.edition_id,
        'event_details': {'start_date': start.isoformat(), 'start_time': start_time,
            'end_date': (start + timedelta(days=days)).isoformat(), 'end_time': end_time,
            'timezone': 'America/Santiago', 'location': location,
            'organizer': 'Comunidad Entre Páginas · Demo', 'category': category},
    }


def complete_publication(payload, book, sequence):
    payload.update(book_ref=post_reference(book.edition_id), book_title=book.title[:200])
    title = book.title[:120]
    kind = payload['publication_type']
    if kind == 'promotion':
        discount = (10, 15, 20)[(sequence // 32) % 3]
        until = datetime.now(ZoneInfo('America/Santiago')).date() + timedelta(days=7)
        payload.update(title=f'Selección de la semana: {title}'[:200],
            body=f'**{discount}% de descuento en {title}** hasta el {until:%d/%m/%Y}. '
                 'Una unidad por persona, hasta agotar 20 ejemplares; no acumulable. '
                 'Cuéntanos si lo elegirías para tu próxima lectura. Oferta ficticia: no se realizan ventas.')
    elif kind == 'launch':
        payload.update(title=f'Presentamos nuestra lectura del mes: {title}'[:200],
            body=f'**{title}** llega a nuestro ciclo de lecturas compartidas. '
                 'Esta semana abrimos las inscripciones y el sábado comentaremos las primeras impresiones, sin spoilers. '
                 '¿Te sumas? Lanzamiento del ciclo demo; no anuncia una nueva edición comercial.')
    elif kind == 'news':
        payload.update(title=f'Nueva lectura compartida: {title}'[:200],
            body=f'Ya elegimos **{title}** para la próxima conversación de la comunidad. '
                 'Publicaremos preguntas durante la semana; puedes participar a tu ritmo. '
                 '¿Lo tienes pendiente o ya lo leíste? Anuncio de demostración.')
    return payload


def publication_files(book, kind):
    """Reuse the actual verified cover; no invented artwork or extra downloads."""
    if kind not in {'event', 'promotion', 'news', 'launch'}:
        return None
    path = cover_path(book.edition_id)
    if not path.is_file():
        return None
    content = path.read_bytes()
    if not valid_image(content):
        return None
    # Upload as a gallery image; the related book independently uses its catalog cover.
    return [('images', ('portada.jpg', content, 'application/octet-stream'))]
