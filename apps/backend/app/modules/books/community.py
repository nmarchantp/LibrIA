"""Live public aggregates, using one current record per reader and logical work."""
from sqlalchemy import func, select

from app.modules.library.models import LibraryEntry, Reading
from app.modules.social.models import Review
from app.modules.users.models import User


def public_rating(db, work_ids):
    from app.modules.books.canonical import enabled
    if enabled():
        from app.modules.books.consistency import current_reviews
        rows = current_reviews(db, work_ids, public=True)
        ratings = [r.rating for r in rows if r.rating is not None and 0.25 <= r.rating <= 5]
        return (sum(ratings) / len(ratings) if ratings else None, len(ratings))
    # Resolve historical duplicate work records without counting a reader twice.
    # Rank before filtering visibility so an older public review cannot reveal a
    # rating after the reader's latest review has become private.
    reviews = select(
        Review.rating, Review.status,
        func.row_number().over(partition_by=Review.created_by_user_id,
            order_by=(Review.updated_at.desc(), Review.id.desc())).label("position"),
    ).where(Review.work_id.in_(work_ids)).subquery()
    return db.execute(select(func.avg(reviews.c.rating), func.count(reviews.c.rating)).where(
        reviews.c.position == 1, reviews.c.status == "published",
        reviews.c.rating.between(0.25, 5),
    )).one()


def reading_statistics(db, work_ids):
    from app.modules.books.canonical import enabled, canonical_members
    if enabled():
        work_ids = set().union(*(canonical_members(db, key) for key in work_ids))
    # Reading attempts are history, not additional readers. The latest attempt
    # across existing equivalent works represents each active library member.
    attempts = select(
        LibraryEntry.user_id, Reading.status,
        func.row_number().over(partition_by=LibraryEntry.user_id,
            order_by=(Reading.created_at.desc(), Reading.id.desc())).label("position"),
    ).join(Reading, Reading.library_entry_id == LibraryEntry.id).where(
        Reading.work_id.in_(work_ids), LibraryEntry.archived_at.is_(None),
    ).subquery()
    counts = dict(db.execute(select(attempts.c.status, func.count()).where(
        attempts.c.position == 1).group_by(attempts.c.status)).all())
    finished = select(attempts.c.user_id).where(attempts.c.position == 1, attempts.c.status == "finished")
    preview = db.execute(select(User.display_name, User.avatar_url).where(User.id.in_(finished))
                         .order_by(User.display_name, User.id).limit(6)).all()
    return {
        "finished": counts.get("finished", 0),
        "reading": counts.get("reading", 0),
        "abandoned": counts.get("abandoned", 0),
        "readerPreview": [{"displayName": name, "avatarUrl": avatar} for name, avatar in preview],
    }
