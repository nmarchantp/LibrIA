"""Idempotent social interactions; callers own the transaction."""
from sqlalchemy import select, func
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import insert
from app.modules.social.models import ActivityView, ReadingEventLike, PostLike, ReviewLike, PostComment
from app.modules.social.activity_access import resolve_activity
from app.modules.users.identity_models import Profile

DESTINATIONS = {
    "publication": (PostLike, "post_id"), "review": (ReviewLike, "review_id"),
    "reading_event": (ReadingEventLike, "reading_event_id"),
}


def capabilities(viewer_id, owners, can_comment=False):
    return {"can_like": True, "can_comment": can_comment, "can_view": True, "can_register_view": viewer_id not in owners}


def batch_counts(db, groups, viewer_id):
    result = {}
    for kind, identifiers in groups.items():
        if not identifiers:
            continue
        model, field = DESTINATIONS[kind]
        target = getattr(model, field)
        likes = dict(db.execute(select(target, func.count()).where(target.in_(identifiers)).group_by(target)).all())
        liked = set(db.scalars(select(target).where(target.in_(identifiers), model.user_id == viewer_id)))
        comment_target, view_target = getattr(PostComment, field), getattr(ActivityView, field)
        comments = dict(db.execute(select(comment_target, func.count()).where(comment_target.in_(identifiers)).group_by(comment_target)).all())
        views = dict(db.execute(select(view_target, func.count()).where(view_target.in_(identifiers)).group_by(view_target)).all())
        result.update({(kind, identifier): {"like_count": likes.get(identifier, 0), "liked_by_me": identifier in liked,
            "comment_count": comments.get(identifier, 0), "view_count": views.get(identifier, 0)} for identifier in identifiers})
    return result


def stats(db, kind, identifier, viewer_id, owners):
    can_comment = db.scalar(select(Profile.id).where(Profile.owner_user_id == viewer_id)) is not None
    return {**batch_counts(db, {kind: [identifier]}, viewer_id)[(kind, identifier)],
            "capabilities": capabilities(viewer_id, owners, can_comment), "observed_at": datetime.now(timezone.utc).isoformat(timespec="microseconds")}


def record_view(db, kind, identifier, viewer_id, owners):
    if viewer_id in owners:
        return
    field = DESTINATIONS[kind][1]
    db.execute(insert(ActivityView).values(user_id=viewer_id, **{field: identifier}).on_conflict_do_nothing())


def like(db, kind, identifier, viewer_id, enabled):
    _, owners = resolve_activity(db, kind, identifier, lock=True)
    model, field = DESTINATIONS[kind]
    target = getattr(model, field)
    if enabled:
        db.execute(insert(model).values(user_id=viewer_id, **{field: identifier}).on_conflict_do_nothing())
        record_view(db, kind, identifier, viewer_id, owners)
    else:
        db.query(model).filter(target == identifier, model.user_id == viewer_id).delete(synchronize_session=False)
    return stats(db, kind, identifier, viewer_id, owners)


def add_comment(db, kind, identifier, viewer_id, profile_id, body):
    _, owners = resolve_activity(db, kind, identifier, lock=True)
    comment = PostComment(user_id=viewer_id, author_profile_id=profile_id, body=body,
                          **{DESTINATIONS[kind][1]: identifier})
    db.add(comment)
    db.flush()
    record_view(db, kind, identifier, viewer_id, owners)
    return comment, stats(db, kind, identifier, viewer_id, owners)
