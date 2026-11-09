"""Shared visibility policy for mural queries and every interaction route."""
from fastapi import HTTPException
from sqlalchemy import and_, case, or_, select, func
from sqlalchemy.orm import aliased
from app.modules.social.models import Post, Review, PostComment
from app.modules.library.models import Reading, ReadingEvent
from app.modules.users.identity_models import Profile


def visible_posts():
    return and_(Post.deleted_at.is_(None), Post.moderation_status == 'approved', Post.moderation_hidden.is_(False), Post.source.in_(("community", "event")),
                or_(Post.author_role != "lector", Post.publication_type.in_(("note", "theory"))))


def visible_reading_events():
    abandoned = aliased(ReadingEvent)
    shared = select(abandoned.id).where(abandoned.reading_id == Reading.id,
        abandoned.kind == "abandon", abandoned.is_public).correlate(Reading).exists()
    return and_(ReadingEvent.is_public, or_(Reading.status != "abandoned", shared))


def public_reviews(db):
    query = select(Review)
    from app.modules.books.canonical import enabled, identity_snapshot
    if enabled():
        from app.modules.books.consistency import review_preferences
        snapshot = identity_snapshot(db)
        redirects = {key: value.canonical_work_id for key, value in snapshot.mapping.items() if key != value.canonical_work_id}
        root = case(redirects, value=Review.work_id, else_=Review.work_id) if redirects else Review.work_id
        preferred = review_preferences(db, snapshot)
        if preferred:
            wanted = case(*[(and_(Review.author_profile_id == profile, root == work), review)
                            for (profile, work), review in preferred.items()], else_=None)
            query = query.where(or_(wanted.is_(None), Review.id == wanted))
        ranked = query.with_only_columns(Review.id.label("id"), func.row_number().over(
            partition_by=(Review.author_profile_id, root), order_by=(Review.updated_at.desc(), Review.id.desc())).label("position")).subquery()
        query = select(Review).join(ranked, ranked.c.id == Review.id).where(ranked.c.position == 1)
    return query.where(Review.status == "published", Review.moderation_status == 'approved', Review.moderation_hidden.is_(False))


def visible_comments():
    return and_(PostComment.moderation_status == 'approved', PostComment.moderation_hidden.is_(False), PostComment.deleted_at.is_(None))


MODELS = {"publication": Post, "review": Review, "reading_event": ReadingEvent}


def resolve_activity(db, kind, identifier, *, lock=False):
    model = MODELS[kind]
    query = select(model).where(model.id == identifier).execution_options(populate_existing=True)
    if lock:
        query = query.with_for_update()
    record = db.scalar(query)
    if record is None:
        raise HTTPException(404, "Actividad no encontrada")
    if kind == "publication":
        allowed = db.scalar(select(Post.id).where(Post.id == identifier, visible_posts()))
        owners = {record.user_id}
    elif kind == "review":
        allowed = db.scalar(public_reviews(db).with_only_columns(Review.id).where(Review.id == identifier))
        owners = {record.created_by_user_id}
    else:
        reading_query = select(Reading).where(Reading.id == record.reading_id)
        if lock:
            reading_query = reading_query.with_for_update()
        db.scalar(reading_query.execution_options(populate_existing=True))
        allowed = db.scalar(select(ReadingEvent.id).join(Reading, Reading.id == ReadingEvent.reading_id)
                            .where(ReadingEvent.id == identifier, visible_reading_events()))
        owners = {record.actor_user_id}
    if allowed is None:
        raise HTTPException(404, "Actividad no encontrada")
    if kind != "reading_event" and record.author_profile_id:
        owner = db.scalar(select(Profile.owner_user_id).where(Profile.id == record.author_profile_id))
        if owner:
            owners.add(owner)
    return record, owners


def resolve_legacy(db, identifier, *, lock=False):
    kinds = [kind for kind, model in MODELS.items() if db.scalar(select(model.id).where(model.id == identifier))]
    if len(kinds) > 1:
        raise HTTPException(409, "Usa el tipo de actividad para identificar este contenido")
    if not kinds:
        raise HTTPException(404, "Contenido no encontrado")
    resolve_activity(db, kinds[0], identifier, lock=lock)
    return kinds[0]
