"""Queries that resolve multiple catalog records to one logical work."""
from datetime import date
import re

from sqlalchemy import func, select, text

from app.modules.books.identity import bibliographic_title, canonical_author_name, canonical_title_variants, canonical_work_key, duplicate_candidate, identity_matches
from app.modules.books.models import Author, CatalogSource, Edition, Work, WorkAuthor


def equivalent_work_ids(db, work_id):
    """Logical grouping only, using source-level, known author evidence.

    An anonymous edition in a contaminated Work cannot inherit its author's
    identity. Conflicting or missing provider authors quarantine that Work.
    """
    if db.get(Work, work_id) is None:
        return set()
    author_rows = db.execute(select(WorkAuthor.work_id, Author.name)
                             .join(Author, Author.id == WorkAuthor.author_id)).all()
    authors = {}
    for identifier, name in author_rows:
        authors.setdefault(identifier, []).append(name)
    rows = db.execute(select(Edition, CatalogSource).outerjoin(
        CatalogSource, CatalogSource.edition_id == Edition.id)).all()
    evidence = {}
    for edition, source in rows:
        record = evidence.setdefault(edition.work_id, {"titles": set(), "authors": set(), "unknown": False})
        if source and source.provider in {"google-books", "open-library"}:
            payload = source.payload or {}
            info = payload.get("volumeInfo") or {}
            names = info.get("authors") or []
            record["titles"].update(canonical_title_variants(bibliographic_title(info) or edition.title))
        elif source is None:
            names = authors.get(edition.work_id, [])
            record["titles"].update(canonical_title_variants(edition.title))
        else:
            continue
        normalized = [canonical_author_name(name) for name in names]
        if not normalized or not all(normalized):
            record["unknown"] = True
        else:
            record["authors"].add(tuple(sorted(set(normalized))))
    selected = evidence.get(work_id)
    if not selected or selected["unknown"] or len(selected["authors"]) != 1:
        return {work_id}
    matches = {work_id}
    known_titles = set(selected["titles"])
    changed = True
    while changed:
        changed = False
        for identifier, candidate in evidence.items():
            if (identifier not in matches and not candidate["unknown"]
                    and candidate["authors"] == selected["authors"]
                    and candidate["titles"] & known_titles):
                matches.add(identifier)
                known_titles.update(candidate["titles"])
                changed = True
    return matches


def verified_work_for_import(db, title, names):
    """Resolve legacy identity keys by evidence, never by an obsolete key alone."""
    if not canonical_work_key(title, names):
        return None
    rows = db.execute(select(Edition, CatalogSource).join(
        CatalogSource, CatalogSource.edition_id == Edition.id).where(
        CatalogSource.provider.in_(["google-books", "open-library"]))).all()
    candidates, unsafe = set(), set()
    incoming = {canonical_author_name(name) for name in names}
    for edition, source in rows:
        info = (source.payload or {}).get("volumeInfo") or {}
        authors = info.get("authors") or []
        normalized = {canonical_author_name(name) for name in authors}
        if not normalized or "" in normalized or normalized != incoming:
            unsafe.add(edition.work_id)
        if identity_matches(title, names, bibliographic_title(info) or edition.title, authors):
            candidates.add(edition.work_id)
    candidates -= unsafe
    # Ambiguous matches require review rather than selecting an arbitrary Work.
    return db.get(Work, next(iter(candidates))) if len(candidates) == 1 else None


def duplicate_work_candidates(db, work_id):
    """Read-only review report, deliberately separate from identity resolution."""
    work = db.get(Work, work_id)
    if work is None:
        return []
    authors = {}
    for identifier, name in db.execute(select(WorkAuthor.work_id, Author.name)
            .join(Author, Author.id == WorkAuthor.author_id)).all():
        authors.setdefault(identifier, []).append(name)
    return [{"workId": str(candidate.id), "title": candidate.title,
             "reason": "similar_title_requires_bibliographic_review"}
            for candidate in db.scalars(select(Work).where(Work.id != work_id)).all()
            if duplicate_candidate(work.title, authors.get(work_id, []),
                                   candidate.title, authors.get(candidate.id, []))]


def verified_original_publication(db, work_id):
    """Only editorial provenance can attest the legacy original-date field.

    Provider edition dates and existing unverified values are never evidence.
    No verification records are created by catalog imports.
    """
    work = db.get(Work, work_id)
    if not work or not work.first_publication_date:
        return None
    value = work.first_publication_date
    if not re.fullmatch(r"\d{4}(?:-\d{2})?(?:-\d{2})?", value):
        return None
    try:
        parts = [int(part) for part in value.split("-")]
        date(*(parts + [1] * (3 - len(parts))))
    except ValueError:
        return None
    sources = db.scalars(select(CatalogSource).join(Edition, CatalogSource.edition_id == Edition.id)
        .where(Edition.work_id == work_id, CatalogSource.provider == "libria-verification",
               CatalogSource.validation_status == "validated")).all()
    for source in sources:
        proof = (source.payload or {}).get("originalPublication", {})
        if (isinstance(proof, dict) and proof.get("workId") == str(work_id)
                and proof.get("date") == work.first_publication_date
                and isinstance(proof.get("evidenceUrl"), str)
                and proof["evidenceUrl"].startswith("https://")
                and proof.get("verifiedBy") and proof.get("verifiedAt")):
            return work.first_publication_date
    return None


def consolidate_equivalent_works(db, work_id, *, reviewed=False):
    """Move every dependent record to one Work and delete physical duplicates.

    The most-used Work wins, so existing public/library references remain stable.
    If one profile reviewed two duplicates, consolidation is postponed because
    choosing which of those two reviews to discard requires an editorial decision.
    """
    if not reviewed:
        return work_id
    work_ids = equivalent_work_ids(db, work_id)
    if len(work_ids) < 2:
        return work_id
    ids = sorted(work_ids, key=str)
    for value in ids:
        db.execute(select(func.pg_advisory_xact_lock(func.hashtext("catalog:merge:" + str(value)))))
    ranked = db.execute(text("""
        SELECT w.id,
          (SELECT count(*) FROM app.entradas_biblioteca b WHERE b.work_id=w.id) * 1000 +
          (SELECT count(*) FROM app.resenas r WHERE r.work_id=w.id) * 1000 +
          (SELECT count(*) FROM app.ediciones e WHERE e.work_id=w.id) AS weight
        FROM app.obras w WHERE w.id = ANY(:ids) ORDER BY weight DESC, w.created_at, w.id
    """), {"ids": ids}).all()
    target = ranked[0].id
    duplicates = [row.id for row in ranked[1:]]
    collision = db.scalar(text("""
        SELECT EXISTS (
          SELECT 1 FROM app.resenas WHERE work_id = ANY(:ids)
          GROUP BY author_profile_id HAVING count(*) > 1)
    """), {"ids": ids})
    if collision:
        db.execute(text("""UPDATE app.fuentes_catalogo SET consolidation_status='pending_review_conflict'
            WHERE edition_id IN (SELECT id FROM app.ediciones WHERE work_id = ANY(:ids))"""), {"ids": ids})
        return target

    db.execute(text("SET LOCAL app.catalog_merge = 'on'"))
    # Constraint names live in the ``app`` schema and PostgreSQL resolves named
    # SET CONSTRAINTS entries through search_path. ALL reliably addresses every
    # deferrable constraint in the current transaction.
    db.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    for duplicate in duplicates:
        # Coalesce the same user's two library entries without losing reading attempts.
        pairs = db.execute(text("""
            SELECT old.id AS old_id, current.id AS current_id
            FROM app.entradas_biblioteca old JOIN app.entradas_biblioteca current
              ON current.user_id=old.user_id AND current.work_id=:target
            WHERE old.work_id=:duplicate
        """), {"target": target, "duplicate": duplicate}).all()
        db.execute(text("UPDATE app.lecturas SET work_id=:target WHERE work_id=:duplicate"),
                   {"target": target, "duplicate": duplicate})
        for pair in pairs:
            db.execute(text("UPDATE app.lecturas SET library_entry_id=:current WHERE library_entry_id=:old"),
                       {"current": pair.current_id, "old": pair.old_id})
            db.execute(text("DELETE FROM app.entradas_biblioteca WHERE id=:old"), {"old": pair.old_id})
        db.execute(text("UPDATE app.entradas_biblioteca SET work_id=:target WHERE work_id=:duplicate"),
                   {"target": target, "duplicate": duplicate})
        db.execute(text("UPDATE app.resenas SET work_id=:target WHERE work_id=:duplicate"),
                   {"target": target, "duplicate": duplicate})
        db.execute(text("UPDATE app.ediciones SET work_id=:target WHERE work_id=:duplicate"),
                   {"target": target, "duplicate": duplicate})
        db.execute(text("UPDATE app.publicaciones SET work_id=:target WHERE work_id=:duplicate"),
                   {"target": target, "duplicate": duplicate})
        db.execute(text("""
            INSERT INTO app.obras_autores(work_id,author_id,position)
            SELECT :target,author_id,position FROM app.obras_autores WHERE work_id=:duplicate
            ON CONFLICT (work_id,author_id) DO NOTHING
        """), {"target": target, "duplicate": duplicate})
        db.execute(text("""
            INSERT INTO app.titulos_alternativos(id,work_id,title,normalized_title,language,created_at)
            SELECT gen_random_uuid(),:target,title,normalized_title,language,created_at
            FROM app.titulos_alternativos WHERE work_id=:duplicate
            ON CONFLICT (work_id,normalized_title,language) DO NOTHING
        """), {"target": target, "duplicate": duplicate})
        db.execute(text("DELETE FROM app.obras WHERE id=:duplicate"), {"duplicate": duplicate})
    db.flush()
    return target
