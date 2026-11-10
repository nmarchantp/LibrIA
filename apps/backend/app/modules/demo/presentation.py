"""Show the selected showcase editions without altering stored user activity."""
import uuid
from sqlalchemy import or_, true

from app.modules.demo.models import DemoMode
from app.modules.demo.covers import cover_path
from app.modules.demo.service import PERSONAS, identifier

DEMO_USERS = {identifier('user:' + key) for key, _, _ in PERSONAS}


def visible_demo_selection(db, owner_column, edition_column):
    mode = db.get(DemoMode, 1)
    selected = mode.catalog_edition_ids if mode else []
    if not selected or not any(cover_path(value).is_file() for value in selected):
        return true()
    return or_(owner_column.not_in(DEMO_USERS), edition_column.in_([uuid.UUID(value) for value in selected]))
