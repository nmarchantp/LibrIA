"""Community-readable tastes, written only through the authenticated account."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.identities import personal_profile
from app.modules.users.identity_models import Profile
from app.modules.users.models import User
from app.modules.users.preference_models import FavoriteGenre, FavoriteTrope, Genre, Trope, IntensityCategory, FavoriteIntensity, Interest, FavoriteInterest
from app.modules.users.preference_schemas import LiteraryPreferences, PreferenceCatalogs, PreferencesUpdate, PublicProfile
from app.modules.users.preference_schemas import ReadingGenreStatistics
from app.modules.users.reading_statistics import most_read_genres

router = APIRouter(prefix="/profiles", tags=["profiles"])
SessionDB = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def intensity_option(item):
    return {"id": item.id, "name": item.name, "icon": item.icon, "color": item.color, "levels": item.levels}


def choices(db, user_id):
    genres = db.scalars(select(Genre).join(FavoriteGenre, Genre.id == FavoriteGenre.genre_id)
                        .where(FavoriteGenre.user_id == user_id).order_by(FavoriteGenre.position)).all()
    tropes = db.scalars(select(Trope).join(FavoriteTrope, Trope.id == FavoriteTrope.trope_id)
                        .where(FavoriteTrope.user_id == user_id).order_by(Trope.sort_order, Trope.id)).all()
    intensities = db.execute(select(IntensityCategory, FavoriteIntensity.level, FavoriteIntensity.featured)
        .join(FavoriteIntensity, IntensityCategory.id == FavoriteIntensity.category_id)
        .where(FavoriteIntensity.user_id == user_id).order_by(FavoriteIntensity.position)).all()
    interests = db.scalars(select(Interest).join(FavoriteInterest, Interest.id == FavoriteInterest.interest_id)
        .where(FavoriteInterest.user_id == user_id).order_by(Interest.sort_order, Interest.id)).all()
    return {"featured_category_id": next((item.id for item, _, featured in intensities if featured), None),
            "intensities": [{**intensity_option(item), "level": level} for item, level, _ in intensities],
            "interests": [{"id": x.id, "name": x.name, "group": x.group_name} for x in interests],
            "genres": [{"id": x.id, "name": x.name, "group": x.group_name} for x in genres],
            "tropes": [{"id": x.id, "name": x.name, "group": x.group_name} for x in tropes]}


def own_response(db, user):
    profile = personal_profile(db, user)
    return {"profile_id": profile.id, "biography": user.biography, **choices(db, user.id)}


@router.get("/preference-catalogs", response_model=PreferenceCatalogs)
def catalogs(user: CurrentUser, db: SessionDB):
    result = {key: [{"id": x.id, "name": x.name, "group": x.group_name} for x in db.scalars(
        select(model).where(model.active.is_(True)).order_by(model.sort_order, model.id))]
        for key, model in (("genres", Genre), ("tropes", Trope), ("interests", Interest))}
    result["intensities"] = [intensity_option(x) for x in db.scalars(select(IntensityCategory)
        .where(IntensityCategory.active.is_(True)).order_by(IntensityCategory.sort_order, IntensityCategory.id))]
    return result


@router.get("/me/literary-preferences", response_model=LiteraryPreferences)
def my_preferences(user: CurrentUser, db: SessionDB):
    return own_response(db, user)


@router.get("/me/reading-genres", response_model=ReadingGenreStatistics)
def my_reading_genres(user: CurrentUser, db: SessionDB):
    return most_read_genres(db, user.id)


@router.patch("/me/literary-preferences", response_model=LiteraryPreferences)
def update_preferences(data: PreferencesUpdate, user: CurrentUser, db: SessionDB):
    # Serialize simultaneous saves for this account; validate before any mutation.
    owner = db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    personal_profile(db, owner)
    supplied = data.model_fields_set
    for field, model, association, column in (
        ("genre_ids", Genre, FavoriteGenre, FavoriteGenre.genre_id),
        ("trope_ids", Trope, FavoriteTrope, FavoriteTrope.trope_id),
        ("interest_ids", Interest, FavoriteInterest, FavoriteInterest.interest_id),
        ("intensities", IntensityCategory, FavoriteIntensity, FavoriteIntensity.category_id),
    ):
        if field not in supplied:
            continue
        ids = [x.category_id for x in data.intensities] if field == "intensities" else getattr(data, field)
        available = set(db.scalars(select(model.id).where(model.id.in_(ids), model.active.is_(True))))
        # Existing retired labels can be kept or removed, but not newly selected.
        existing = set(db.scalars(select(column).where(association.user_id == owner.id)))
        if set(ids) - available - existing:
            raise HTTPException(status_code=422, detail="La selección contiene identificadores desconocidos o inactivos")
    current_intensities = db.execute(select(FavoriteIntensity.category_id, FavoriteIntensity.featured)
        .where(FavoriteIntensity.user_id == owner.id)).all()
    selected_ids = {item.category_id for item in data.intensities} if "intensities" in supplied else {item.category_id for item in current_intensities}
    previous_featured = next((item.category_id for item in current_intensities if item.featured), None)
    if "featured_category_id" in supplied:
        featured_id = data.featured_category_id
        if featured_id is not None and featured_id not in selected_ids:
            raise HTTPException(status_code=422, detail="El gusto destacado debe ser una categoría configurada")
    else:
        featured_id = previous_featured if previous_featured in selected_ids else None
    try:
        if "biography" in supplied:
            owner.biography = data.biography or None
        if "genre_ids" in supplied:
            db.execute(delete(FavoriteGenre).where(FavoriteGenre.user_id == owner.id))
            db.add_all(FavoriteGenre(user_id=owner.id, genre_id=value, position=i) for i, value in enumerate(data.genre_ids, 1))
        if "trope_ids" in supplied:
            db.execute(delete(FavoriteTrope).where(FavoriteTrope.user_id == owner.id))
            db.add_all(FavoriteTrope(user_id=owner.id, trope_id=value) for value in data.trope_ids)
        if "intensities" in supplied:
            db.execute(delete(FavoriteIntensity).where(FavoriteIntensity.user_id == owner.id))
            db.add_all(FavoriteIntensity(user_id=owner.id, category_id=item.category_id, level=item.level, position=i, featured=item.category_id == featured_id)
                       for i, item in enumerate(data.intensities, 1))
        elif "featured_category_id" in supplied:
            # Clear first so changing the featured category never temporarily
            # violates the partial unique index, regardless of row update order.
            db.execute(update(FavoriteIntensity).where(FavoriteIntensity.user_id == owner.id).values(featured=False))
            if featured_id is not None:
                db.execute(update(FavoriteIntensity).where(FavoriteIntensity.user_id == owner.id,
                    FavoriteIntensity.category_id == featured_id).values(featured=True))
        if "interest_ids" in supplied:
            db.execute(delete(FavoriteInterest).where(FavoriteInterest.user_id == owner.id))
            db.add_all(FavoriteInterest(user_id=owner.id, interest_id=value) for value in data.interest_ids)
        db.flush()
        result = own_response(db, owner)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


@router.get("/{profile_id}", response_model=PublicProfile)
def community_profile(profile_id: uuid.UUID, user: CurrentUser, db: SessionDB):
    profile = db.get(Profile, profile_id)
    if profile is None or profile.kind != "personal":
        raise HTTPException(status_code=404, detail="Perfil personal no encontrado")
    owner = db.get(User, profile.owner_user_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Perfil personal no encontrado")
    return {"id": profile.id, "display_name": owner.display_name, "avatar_url": owner.avatar_url,
            "biography": owner.biography, **choices(db, owner.id)}
