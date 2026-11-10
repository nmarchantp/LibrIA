"""A private profile is unlocked only when its owner follows the visitor."""
from sqlalchemy import select
from app.modules.users.identity_models import Profile
from app.modules.social.models import ProfileFollow


def profile_access(db, owner, viewer):
    if owner.id == viewer.id or owner.profile_visibility == 'public':
        return True
    visitor_profile = db.scalar(select(Profile.id).where(Profile.owner_user_id == viewer.id, Profile.kind == 'personal'))
    return visitor_profile is not None and db.get(ProfileFollow, (visitor_profile, owner.id)) is not None
