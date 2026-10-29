"""Shared exact work matching for incorporation and discovery."""
from sqlalchemy import select

from app.modules.books.identity import identity_matches
from app.modules.books.models import Author, Edition, Work, WorkAuthor


def matching_work(db, title, authors, *, reject_ambiguous=False):
    names = {}
    for work_id, name in db.execute(select(WorkAuthor.work_id, Author.name).join(
            Author, Author.id == WorkAuthor.author_id)):
        names.setdefault(work_id, []).append(name)
    titles = {}
    for work_id, edition_title in db.execute(select(Edition.work_id, Edition.title)):
        titles.setdefault(work_id, []).append(edition_title)
    matches = [work for work in db.scalars(select(Work)) if any(
        identity_matches(title, authors, candidate, names.get(work.id, []))
        for candidate in [work.title, *titles.get(work.id, [])])]
    if not matches:
        return None
    from app.modules.books.canonical import resolve_canonical_work
    roots = {resolve_canonical_work(db, work.id).canonical_work_id for work in matches}
    if len(roots) > 1 and reject_ambiguous:
        from app.modules.books.evidence import BibliographicDataError
        raise BibliographicDataError("Hay varias obras con este título y autores. Revisa su agrupación en el mantenedor antes de crear otra.")
    return db.get(Work, roots.pop()) if len(roots) == 1 else None
