"""Remove expired media in bounded batches; API expiry is immediate."""
from sqlalchemy import select, delete, func
from app.modules.social.story_models import Story


def purge_expired_stories(db, batch_size=200):
    expired = select(Story.id).where(Story.expires_at <= func.now()).order_by(Story.expires_at).limit(batch_size).with_for_update(skip_locked=True)
    return db.execute(delete(Story).where(Story.id.in_(expired))).rowcount
