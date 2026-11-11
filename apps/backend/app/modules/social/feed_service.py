"""Read-only category projections. Privacy and ranking precede keyset pagination."""
import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_, select, tuple_
from sqlalchemy.orm import aliased

from app.core.config import get_settings
from app.modules.books.models import Author, CatalogSource, Edition, Work, WorkAuthor
from app.modules.library.models import Reading, ReadingEvent
from app.modules.social.models import Post, PostBookCover, PostImage, PostLike, ProfileFollow, Review, ReviewLike
from app.modules.social.post_covers import cover_url
from app.modules.social.event_service import batch_event_details
from app.modules.social.router import as_reading_response, as_response
from app.modules.social.activity_access import visible_posts, visible_reading_events, public_reviews
from app.modules.social.interaction_service import batch_counts, capabilities
from app.modules.social.schemas import PostResponse
from app.modules.users.identity_models import Profile, ProfileMember
from app.modules.users.models import User

CATEGORIES = ("progress", "started", "finished", "reviews", "social")
PUBLICATION_CATEGORIES = {"events": "event", "launches": "launch", "announcements": "news", "promotions": "promotion"}


def encode_cursor(data):
    raw = json.dumps(data, separators=(",", ":")).encode()
    signature = hmac.new(get_settings().jwt_secret.encode(), raw, hashlib.sha256).hexdigest().encode()
    return base64.urlsafe_b64encode(signature + b"." + raw).decode()


def decode_cursor(token, user_id, audience, category):
    try:
        signed, raw = base64.urlsafe_b64decode(token).split(b".", 1)
        expected = hmac.new(get_settings().jwt_secret.encode(), raw, hashlib.sha256).hexdigest().encode()
        if not hmac.compare_digest(signed, expected):
            raise ValueError()
        data = json.loads(raw)
        if data["scope"] != [str(user_id), audience, category]:
            raise ValueError()
        snapshot, when = datetime.fromisoformat(data["snapshot"]), datetime.fromisoformat(data["last"][0])
        if snapshot.tzinfo is None or when.tzinfo is None or when > snapshot:
            raise ValueError()
        return snapshot, (when, uuid.UUID(data["last"][1]))
    except (ValueError, KeyError, TypeError, UnicodeError):
        raise HTTPException(422, "El cursor no es válido para esta categoría y audiencia") from None


def query_items(db, user, audience, category, snapshot, limit, after=None, latest=False):
    from app.modules.demo.presentation import visible_demo_selection
    if category in ("progress", "started", "finished"):
        model, date = ReadingEvent, ReadingEvent.created_at
        personal = aliased(Profile)
        query = select(model).join(Reading, Reading.id == model.reading_id).where(
            visible_reading_events(), visible_demo_selection(db, model.actor_user_id, Reading.edition_id),
            model.kind == {"progress": "progress", "started": "start", "finished": "finish"}[category], date <= snapshot)
        if audience == "contacts":
            query = query.where(select(ProfileFollow.user_id).join(personal, personal.id == ProfileFollow.profile_id)
                .where(ProfileFollow.user_id == user.id, personal.kind == "personal",
                       personal.owner_user_id == model.actor_user_id).exists())
        if latest and category == "progress":
            ranked = query.with_only_columns(model.id.label("id"), func.row_number().over(
                partition_by=(model.actor_user_id, model.reading_id), order_by=(date.desc(), model.id.desc())).label("position")).subquery()
            query = select(model).join(ranked, ranked.c.id == model.id).where(ranked.c.position == 1)
    elif category == "reviews":
        model, date = Review, func.coalesce(Review.published_at, Review.created_at)
        query = public_reviews(db).where(date <= snapshot, visible_demo_selection(db, model.created_by_user_id, model.edition_id))
    else:
        model, date = Post, Post.created_at
        query = select(model).where(visible_posts(), date <= snapshot, visible_demo_selection(db, model.user_id, model.edition_id))
        if category in PUBLICATION_CATEGORIES:
            publication_filter = Post.publication_type == PUBLICATION_CATEGORIES[category]
            if category == 'events':
                publication_filter = or_(publication_filter, and_(Post.source == 'event', Post.publication_type.is_(None)))
            query = query.where(publication_filter)
        elif category == 'social':
            # Both preview and history use this predicate before limit/keyset pagination.
            # Keep untyped historical community posts, but never legacy event sources.
            query = query.where(Post.source == 'community',or_(Post.publication_type.is_(None),
                Post.publication_type.not_in(tuple(PUBLICATION_CATEGORIES.values()))))
    if audience == "contacts" and (category in ("reviews", "social") or category in PUBLICATION_CATEGORIES):
        query = query.where(select(ProfileFollow.user_id).where(ProfileFollow.user_id == user.id,
            ProfileFollow.profile_id == model.author_profile_id).exists())
    if after:
        query = query.where(tuple_(date, model.id) < tuple_(*after))
    return list(db.scalars(query.order_by(date.desc(), model.id.desc()).limit(limit)))


def hydrate(db, records, viewer):
    """Bounded batch queries, independent of the number of cards."""
    if not records:
        return {}
    from app.modules.demo.covers import cached_cover_url
    from app.modules.demo.presentation import DEMO_USERS
    events = [r for r in records if isinstance(r, ReadingEvent)]
    readings = {r.id: r for r in db.scalars(select(Reading).where(Reading.id.in_({e.reading_id for e in events})))} if events else {}
    profile_ids = {r.author_profile_id for r in records if not isinstance(r, ReadingEvent) and r.author_profile_id}
    user_ids = {r.actor_user_id if isinstance(r, ReadingEvent) else r.created_by_user_id if isinstance(r, Review) else r.user_id for r in records}
    profiles = list(db.scalars(select(Profile).where(or_(Profile.id.in_(profile_ids), Profile.owner_user_id.in_(user_ids | {viewer.id})))))
    profile_map = {p.id: p for p in profiles}
    editable_profiles = {p.id for p in profiles if p.kind == 'personal' and p.owner_user_id == viewer.id}
    organizations = {p.id for p in profiles if p.kind == 'organization'}
    if organizations:
        editable_profiles.update(db.scalars(select(ProfileMember.profile_id).where(ProfileMember.profile_id.in_(organizations),
            ProfileMember.user_id == viewer.id, ProfileMember.permission == 'admin')))
    personal = {p.owner_user_id: p for p in profiles if p.kind == "personal"}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids | {p.owner_user_id for p in profiles if p.owner_user_id})))}
    works_ids = {r.work_id for r in records if not isinstance(r, ReadingEvent) and r.work_id} | {r.work_id for r in readings.values()}
    edition_ids = {r.edition_id for r in records if not isinstance(r, ReadingEvent) and r.edition_id} | {r.edition_id for r in readings.values() if r.edition_id}
    works = {w.id: w for w in db.scalars(select(Work).where(Work.id.in_(works_ids)))}
    editions = {e.id: e for e in db.scalars(select(Edition).where(Edition.id.in_(edition_ids)))}
    authors = {}
    for work_id, name in db.execute(select(WorkAuthor.work_id, Author.name).join(Author, Author.id == WorkAuthor.author_id)
                                    .where(WorkAuthor.work_id.in_(works_ids)).order_by(WorkAuthor.position)):
        authors.setdefault(work_id, []).append(name)
    references = {}
    for edition_id, reference in db.execute(select(CatalogSource.edition_id, CatalogSource.external_id)
        .where(CatalogSource.edition_id.in_(edition_ids), CatalogSource.provider == "libria-feed").order_by(CatalogSource.external_id)):
        references.setdefault(edition_id, reference)
    follows = set(db.scalars(select(ProfileFollow.profile_id).where(ProfileFollow.user_id == viewer.id,
        ProfileFollow.profile_id.in_(profile_map))))
    posts = [r.id for r in records if isinstance(r, Post)]
    reviews = [r.id for r in records if isinstance(r, Review)]
    calendar_events=batch_event_details(db,posts,viewer.id)
    covers = {cover.post_id: cover for cover in db.execute(select(PostBookCover.post_id,PostBookCover.revision).where(PostBookCover.post_id.in_(posts)))} if posts else {}
    images = {}
    for post_id, image_id in db.execute(select(PostImage.post_id, PostImage.id).where(PostImage.post_id.in_(posts)).order_by(PostImage.created_at, PostImage.id)):
        images.setdefault(post_id, []).append(image_id)
    interactions = batch_counts(db, {"publication": posts, "review": reviews, "reading_event": [e.id for e in events]}, viewer.id)
    observed_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    result = {}
    for record in records:
        reading = readings.get(record.reading_id) if isinstance(record, ReadingEvent) else None
        work_id, edition_id = (reading.work_id, reading.edition_id) if reading else (record.work_id, record.edition_id)
        work, edition = works.get(work_id), editions.get(edition_id)
        user_id = record.actor_user_id if reading else record.created_by_user_id if isinstance(record, Review) else record.user_id
        user = users[user_id]
        profile = personal.get(user_id) if reading else profile_map.get(record.author_profile_id)
        name = profile.display_name if profile else user.display_name
        role = profile.organization_type if profile and profile.kind == "organization" else users.get(profile.owner_user_id, user).role if profile else user.role
        reference = references.get(edition_id) or (str(work_id) if work_id else None)
        if reading:
            item = as_reading_response(record, work.title, user, reference, edition.cover_url if edition else None)
        elif isinstance(record, Review):
            item = PostResponse(id=record.id, feed_item_type="review", user_id=user_id, author=name, author_role=role,
                source="review", kind="reviews", title=None, body=record.body, book_ref=reference,
                book_title=work.title, rating=record.rating, progress_percent=None, reading_event=None,
                dimension_ratings=record.dimension_ratings or {}, is_spoiler=record.is_spoiler,
                status=record.status, published_at=record.published_at, updated_at=record.updated_at,
                revision_number=record.revision_number, created_at=record.published_at or record.created_at,
                moderation_status=record.moderation_status,moderation_version=record.moderation_version)
        else:
            item = as_response(record, name, role, images.get(record.id))
        kind = item.feed_item_type
        result[(kind, record.id)] = {**item.model_dump(), "author_profile_id": profile.id if profile else None,
            "avatar_url": user.avatar_url, "author": name, "author_role": item.author_role,
            "following_author": profile.id in follows if profile else False,
            **interactions[(kind, record.id)],
            "observed_at": observed_at,
            "capabilities": capabilities(viewer.id, {user_id, profile.owner_user_id if profile else None}, viewer.id in personal),
            "work_id": work_id, "edition_id": edition_id, "book_ref": item.book_ref or reference,
            "book_title": item.book_title or (work.title if work else None),
            "book_cover_url": (cached_cover_url(edition_id) if user_id in DEMO_USERS else None) or (edition.cover_url if edition else None), "book_author": ", ".join(authors.get(work_id, [])),
            "custom_book_cover_url": cover_url(covers.get(record.id)) if isinstance(record, Post) else None,
            "event_details": calendar_events.get(record.id) if isinstance(record,Post) and record.publication_type=='event' else None,
            "can_edit_book_cover": isinstance(record, Post) and ((profile and profile.id in editable_profiles) or (not profile and record.user_id == viewer.id)),
            "can_manage": ((isinstance(record, Post) and ((profile and profile.id in editable_profiles) or (not profile and record.user_id == viewer.id))) or (isinstance(record, Review) and record.created_by_user_id == viewer.id and profile.id in editable_profiles)),
            "reading_id": reading.id if reading else None, "page": record.page if reading else None,
            "total_pages": record.total_pages if reading else None}
    return result


def key(record):
    return ("reading_event" if isinstance(record, ReadingEvent) else "review" if isinstance(record, Review) else "publication", record.id)


def page(db, user, audience, category, limit, cursor=None):
    snapshot, after = decode_cursor(cursor, user.id, audience, category) if cursor else (datetime.now(timezone.utc), None)
    records = query_items(db, user, audience, category, snapshot, limit + 1, after)
    has_more, records = len(records) > limit, records[:limit]
    hydrated = hydrate(db, records, user)
    next_cursor = None
    if has_more:
        last = records[-1]
        date = (last.published_at or last.created_at) if isinstance(last, Review) else last.created_at
        next_cursor = encode_cursor({"scope": [str(user.id), audience, category], "snapshot": snapshot.isoformat(), "last": [date.isoformat(), str(last.id)]})
    return {"items": [hydrated[key(r)] for r in records], "next_cursor": next_cursor}


def summary(db, user, audience, limit):
    snapshot = datetime.now(timezone.utc)
    groups = {category: query_items(db, user, audience, category, snapshot, limit + 1, latest=True) for category in CATEGORIES}
    hydrated = hydrate(db, [r for records in groups.values() for r in records[:limit]], user)
    return {"audience": audience, "categories": {category: {"items": [hydrated[key(r)] for r in records[:limit]],
        "has_more": len(records) > limit} for category, records in groups.items()}}
