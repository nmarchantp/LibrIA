from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.library.models import LibraryEntry, Reading
from app.modules.library.challenge_models import ReadingChallenge

router = APIRouter(prefix='/me/reading-challenge', tags=['reading challenge'])
DB = Annotated[Session, Depends(get_db)]
Viewer = Annotated[User, Depends(get_current_user)]
ZONE = ZoneInfo('America/Santiago')


def current_year():
    return datetime.now(ZONE).year


def finished_books(db, user_id, year):
    """Match current library state before filtering year, deduplicated by work."""
    from app.modules.books.canonical import enabled, identity_snapshot
    rows = db.execute(select(Reading.work_id, Reading.status, Reading.finished_at).join(LibraryEntry, Reading.library_entry_id == LibraryEntry.id)
        .where(LibraryEntry.user_id == user_id, LibraryEntry.archived_at.is_(None))
        .order_by(Reading.created_at.desc(), Reading.id.desc())).all()
    snapshot = identity_snapshot(db) if enabled() else None
    latest = {}
    for reading in rows:
        work = snapshot.root(reading.work_id) if snapshot else reading.work_id
        latest.setdefault(work, reading)
    return sum(reading.status == 'finished' and reading.finished_at is not None
               and reading.finished_at.astimezone(ZONE).year == year for reading in latest.values())


def result(db, user, year):
    challenge = db.get(ReadingChallenge, (user.id, year), populate_existing=True)
    finished = finished_books(db, user.id, year)
    target = challenge.target if challenge else None
    percent = min(100, int((Decimal(finished) * 100 / target).quantize(Decimal('1'), rounding=ROUND_HALF_UP))) if target else 0
    return {'year': year, 'target': target, 'finished_books': finished, 'percentage': percent,
            'remaining': max(0, target-finished) if target else None,
            'completed': bool(target and finished >= target), 'exceeded': bool(target and finished > target)}


class ChallengeInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    target: int = Field(strict=True, ge=1, le=1000)


@router.get('')
def get_challenge(db: DB, user: Viewer, response: Response, year: int | None = Query(None, ge=1900, le=9999)):
    response.headers['Cache-Control'] = 'no-store'
    return result(db, user, year if year is not None else current_year())


@router.put('')
def save_challenge(data: ChallengeInput, db: DB, user: Viewer, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    year = current_year()
    db.execute(insert(ReadingChallenge).values(user_id=user.id, year=year, target=data.target)
        .on_conflict_do_update(index_elements=['user_id', 'year'], set_={'target': data.target, 'updated_at': func.now()}))
    db.commit()
    return result(db, user, year)
