"""Queries that resolve multiple catalog records to one logical work."""
from sqlalchemy import func, select, text

from app.modules.books.identity import canonical_author_name, canonical_match_title, canonical_title_variants
from app.modules.books.models import Author, Edition, Work, WorkAuthor


def equivalent_work_ids(db, work_id):
    selected = db.get(Work, work_id)
    if selected is None:
        return set()
    selected_titles = set()
    for title in db.scalars(select(Edition.title).where(Edition.work_id == work_id)):
        selected_titles.update(canonical_match_title(value) for value in canonical_title_variants(title))
    if not selected_titles:
        return {work_id}
    author_rows = db.execute(select(WorkAuthor.work_id, Author.name)
                             .join(Author, Author.id == WorkAuthor.author_id)).all()
    authors = {}
    for author_work_id, name in author_rows:
        authors.setdefault(author_work_id, set()).add(canonical_author_name(name))
    selected_authors = authors.get(work_id, set())
    candidates = db.execute(select(Work.id, Edition.title)
                            .join(Edition, Edition.work_id == Work.id)).all()
    matches = {work_id}
    for candidate_id, title in candidates:
        candidate_authors = authors.get(candidate_id, set())
        if selected_authors and candidate_authors and not selected_authors.intersection(candidate_authors):
            continue
        candidate_titles = {canonical_match_title(value) for value in canonical_title_variants(title)}
        if candidate_titles & selected_titles:
            matches.add(candidate_id)
    # A bilingual record can bridge Spanish and English titles transitively.
    changed = True
    while changed:
        changed = False
        known_titles = set()
        for candidate_id, title in candidates:
            if candidate_id in matches:
                known_titles.update(canonical_match_title(value) for value in canonical_title_variants(title))
        for candidate_id, title in candidates:
            candidate_authors = authors.get(candidate_id, set())
            compatible_author = (not selected_authors or not candidate_authors
                                 or bool(selected_authors.intersection(candidate_authors)))
            if candidate_id not in matches and compatible_author:
                candidate_titles = {canonical_match_title(value) for value in canonical_title_variants(title)}
                if candidate_titles & known_titles:
                    matches.add(candidate_id)
                    changed = True
    return matches


def consolidate_equivalent_works(db, work_id):
    """Move every dependent record to one Work and delete physical duplicates.

    The most-used Work wins, so existing public/library references remain stable.
    If one profile reviewed two duplicates, consolidation is postponed because
    choosing which of those two reviews to discard requires an editorial decision.
    """
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
