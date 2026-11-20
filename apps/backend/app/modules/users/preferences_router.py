"""Community-readable tastes, written only through the authenticated account."""
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
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
    return {"card_order": (user.literary_highlights or {}).get("card_order", []), "literary_crush": (user.literary_highlights or {}).get('literary_crush'), "essential_books": (user.literary_highlights or {}).get('essential_books', []), "profile_visibility": user.profile_visibility, "public_sections": user.public_sections, "story_illustration": user.story_illustration, "favorite_quotes": user.favorite_quotes, "profile_id": profile.id, "biography": user.biography, **choices(db, user.id)}


@router.get("/preference-catalogs", response_model=PreferenceCatalogs)
def catalogs(db: SessionDB):
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
    crush = None
    if 'literary_crush' in supplied and data.literary_crush:
        from app.modules.books.models import LiteraryCharacter, Work
        from app.modules.books.characters_router import character_image
        selection = data.literary_crush
        character = db.get(LiteraryCharacter, selection.character_id)
        if not character or not character.active or character.work_id != selection.work_id:
            raise HTTPException(422, 'Elige un personaje disponible del libro seleccionado')
        work = db.get(Work, character.work_id)
        crush = {'character_id': str(character.id), 'work_id': str(work.id), 'name': character.name,
                 'book': work.title, 'description': selection.description, 'image_url': character_image(character)}
    try:
        highlights = dict(owner.literary_highlights or {})
        if 'literary_crush' in supplied:
            highlights['literary_crush'] = crush
        if 'essential_books' in supplied:
            highlights['essential_books'] = [item.model_dump() for item in data.essential_books]
        if 'card_order' in supplied:
            highlights['card_order'] = data.card_order
        if {'literary_crush', 'essential_books', 'card_order'} & supplied:
            owner.literary_highlights = highlights
        for field in ('profile_visibility', 'public_sections'):
            if field in supplied:
                setattr(owner, field, getattr(data, field))
        if 'public_sections' in supplied:
            owner.events_visibility = 'public' if 'events' in data.public_sections else 'private'
            owner.onboarding = {**(owner.onboarding or {}), 'shared': 'analyses' in data.public_sections}
        if "story_illustration" in supplied:
            owner.story_illustration = data.story_illustration
        if "favorite_quotes" in supplied:
            owner.favorite_quotes = [item if isinstance(item, str) else item.model_dump() for item in data.favorite_quotes]
        if "biography" in supplied:
            from app.modules.users.account_service import audit
            audit(db, owner, owner.id, "profile_updated", before={"biography": owner.biography},
                  after={"biography": data.biography or None})
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


from app.modules.users.onboarding import ProgressUpdate, SharingUpdate, VisualPreference, GuideUpdate


@router.get('/me/onboarding')
def onboarding_progress(user: CurrentUser, db: SessionDB, response: Response):
    from app.modules.users.onboarding import read_progress, EMOTIONS, HABITS
    response.headers['Cache-Control'] = 'private, no-store'
    return {**read_progress(db, user), 'emotions': EMOTIONS, 'habits': HABITS}


@router.patch('/me/onboarding')
def onboarding_save(data: ProgressUpdate, user: CurrentUser, db: SessionDB, response: Response):
    from app.modules.users.onboarding import complete_with_generation
    response.headers['Cache-Control'] = 'private, no-store'
    return complete_with_generation(db, user, data)


@router.patch('/me/onboarding/guide')
def onboarding_guide(data: GuideUpdate, user: CurrentUser, db: SessionDB, response: Response):
    from app.modules.users.onboarding import save_guide
    response.headers['Cache-Control'] = 'private, no-store'
    return save_guide(db, user, data)


@router.post('/me/onboarding/library')
def onboarding_library(user: CurrentUser, db: SessionDB):
    from app.modules.users.onboarding import sync_favorites_library
    return sync_favorites_library(db, user)


@router.patch('/me/onboarding/sharing')
def onboarding_sharing(data: SharingUpdate, user: CurrentUser, db: SessionDB):
    owner = db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    owner.onboarding = {**(owner.onboarding or {}), 'shared': data.shared}
    db.commit()
    return {'shared': data.shared}


@router.patch('/me/onboarding/theme')
def visual_preference(data: VisualPreference, user: CurrentUser, db: SessionDB):
    user.visual_theme = data.theme
    db.commit()
    return {'theme': user.visual_theme}


@router.get('/{profile_id}/literary-dna')
def public_literary_dna(profile_id: uuid.UUID, user: CurrentUser, db: SessionDB, response: Response, preview: bool = False):
    from app.modules.users.profile_access import profile_access
    from app.modules.users.onboarding import read_progress
    response.headers['Cache-Control'] = 'private, no-store'
    profile = db.get(Profile, profile_id)
    owner = db.get(User, profile.owner_user_id) if profile and profile.kind == 'personal' else None
    if not owner or owner.account_status != 'active' or owner.suspended_at or not profile_access(db, owner, user):
        raise HTTPException(404, 'Perfil no disponible')
    if preview and owner.id != user.id:
        raise HTTPException(403, 'Vista previa disponible solo para tu perfil')
    if preview and owner.profile_visibility != 'public':
        return {'dna': None}
    if (preview or owner.id != user.id) and not (owner.onboarding or {}).get('shared', False):
        return {'dna': None}
    state = read_progress(db, owner)
    # Public projection excludes answers, favorites, job state and recommendations.
    dna = state['dna']
    return {'dna': {key: dna[key] for key in ('profile_name', 'profile_description', 'preferred_genres', 'explanation')} if dna else None,
            'generated_at': state['generated_at']}


@router.get('/{profile_id}/showcase/{section}')
def profile_showcase(profile_id: uuid.UUID, section: Literal['library', 'activity', 'analyses'],
                     user: CurrentUser, db: SessionDB, response: Response,
                     preview: bool = False, offset: int = 0, limit: int = 24):
    from app.modules.users.profile_access import profile_access
    response.headers['Cache-Control'] = 'private, no-store'
    profile = db.get(Profile, profile_id)
    owner = db.get(User, profile.owner_user_id) if profile and profile.kind == 'personal' else None
    if not owner or owner.account_status != 'active' or owner.suspended_at:
        raise HTTPException(404, 'Perfil no disponible')
    if preview and owner.id != user.id:
        raise HTTPException(403, 'Vista previa disponible solo para tu perfil')
    allowed = owner.profile_visibility == 'public' if preview else profile_access(db, owner, user)
    if not allowed or section not in (owner.public_sections or []):
        raise HTTPException(403, 'Esta sección no se comparte en Sobre mí')
    if offset < 0 or not 1 <= limit <= 50:
        raise HTTPException(422, 'Paginación no válida')
    if section == 'library':
        from app.modules.books.library_view import library_states
        # Project display fields only: notebooks and reflections remain personal.
        readings = library_states(db, owner.id)
        items = []
        for reading in readings[offset:offset + limit]:
            volume = (reading.catalog_volume or {}).get('volumeInfo', {})
            items.append({'id': str(reading.work_id), 'title': reading.book_title,
                          'authors': volume.get('authors', []),
                          'cover_url': (volume.get('imageLinks') or {}).get('thumbnail'),
                          'status': reading.status, 'progress_percent': reading.progress_percent})
        counts = {status: sum(reading.status == status for reading in readings)
                  for status in ('pending', 'reading', 'finished', 'abandoned')}
        return {'items': items, 'has_more': offset + limit < len(readings), 'total': len(readings), 'counts': counts}
    if section == 'activity':
        from app.modules.social.models import Post
        from app.modules.social.activity_access import visible_posts
        rows = db.scalars(select(Post).where(Post.user_id == owner.id, visible_posts(),
            Post.publication_type.in_(['note', 'theory'])).order_by(Post.created_at.desc(), Post.id.desc())
            .offset(offset).limit(limit + 1)).all()
        return {'items': [{'id': str(row.id), 'title': row.title, 'body': row.body,
                          'publication_type': row.publication_type, 'book_title': row.book_title}
                         for row in rows[:limit]], 'has_more': len(rows) > limit}
    from app.core.config import get_settings
    from app.modules.analytics.reader_dna import read_current_dna
    from app.modules.analytics.models import AIAnalysis
    dna = read_current_dna(db, owner.id, get_settings())
    analysis = db.get(AIAnalysis, dna['analysis_id']) if dna else None
    content = ((analysis.content or {}).get('profile') or {}) if analysis else {}
    keys = ('narrative_preferences', 'character_preferences',
            'themes_and_conflicts', 'emotional_patterns', 'rating_patterns',
            'genres_and_styles', 'interests_from_notes_and_theories',
            'favorite_genres', 'favorite_tropes')
    # Do not publish evidence, source notes, prompts, feedback or job metadata.
    published = {key: [item for item in content[key] if isinstance(item, str)]
                 for key in keys if isinstance(content.get(key), list)}
    if isinstance(content.get('interpretation'), str):
        published['interpretation'] = content['interpretation']
    essence = content.get('reader_essence')
    if isinstance(essence, dict):
        published['reader_essence'] = {key: essence[key] for key in
            ('archetype', 'summary', 'traits', 'evidence_level') if key in essence}
    from app.modules.analytics.recommendation_sync import recommendation_state
    state = recommendation_state(db, owner.id, enqueue=False)
    recommendations = state.get('recommendations') or []
    if isinstance(recommendations, dict):
        recommendations = recommendations.get('recommendations') or []
    if not recommendations:
        from app.modules.users.onboarding import read_progress
        recommendations = read_progress(db, owner).get('recommendations') or []
    return {'profile': published, 'recommendations': [
        {key: item[key] for key in ('work_id', 'title', 'authors', 'cover_url', 'explanation') if key in item}
        for item in recommendations if isinstance(item, dict)]}


@router.get("/{profile_id}", response_model=PublicProfile)
def community_profile(profile_id: uuid.UUID, user: CurrentUser, db: SessionDB, response: Response, preview: bool = False):
    from app.modules.users.profile_access import profile_access
    from app.modules.social.models import ProfileFollow
    response.headers['Cache-Control'] = 'private, no-store'
    profile = db.get(Profile, profile_id)
    if profile is None or profile.kind != "personal":
        raise HTTPException(status_code=404, detail="Perfil personal no encontrado")
    owner = db.get(User, profile.owner_user_id)
    if owner is None or owner.account_status != 'active' or owner.suspended_at:
        raise HTTPException(status_code=404, detail="Perfil personal no encontrado")
    if preview and owner.id != user.id:
        raise HTTPException(403, 'Vista previa disponible solo para tu perfil')
    allowed = owner.profile_visibility == 'public' if preview else profile_access(db, owner, user)
    sections = owner.public_sections if allowed else []
    visitor = db.scalar(select(Profile.id).where(Profile.owner_user_id == user.id, Profile.kind == 'personal'))
    values = choices(db, owner.id) if allowed else {}
    return {"id": profile.id, "display_name": owner.display_name, "avatar_url": owner.avatar_url,
            "profile_visibility": owner.profile_visibility, "can_view": allowed, "is_owner": owner.id == user.id,
            "following": db.get(ProfileFollow, (profile.id, user.id)) is not None,
            "follows_you": visitor is not None and db.get(ProfileFollow, (visitor, owner.id)) is not None,
            "card_order": (owner.literary_highlights or {}).get("card_order", []) if allowed else [],
            "visible_sections": sections, "story_illustration": owner.story_illustration if 'biography' in sections else 'none',
            "biography": owner.biography if 'biography' in sections else None,
            "literary_crush": (owner.literary_highlights or {}).get('literary_crush') if 'biography' in sections else None,
            "essential_books": (owner.literary_highlights or {}).get('essential_books', []) if 'biography' in sections else [],
            "favorite_quotes": owner.favorite_quotes if 'favorite_quotes' in sections else [],
            "featured_category_id": values.get('featured_category_id') if 'intensities' in sections else None,
            **{key: values.get(key, []) if key in sections else [] for key in ('genres', 'tropes', 'intensities', 'interests')}}
