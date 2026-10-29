"""Shared incorporation commands, reached through the opt-in public facade.

Caller owns the outer transaction. No helper commits, performs HTTP, mutates
historical catalog metadata, creates redirects, or chooses a default edition.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import logging
import uuid

from sqlalchemy import func, inspect, or_, select
from sqlalchemy.orm import Session

from app.modules.books.canonical import canonical_members, lock_catalog_writes, lock_publication, resolve_canonical_work
from app.modules.books.catalog_models import CatalogIncorporation, CatalogOperation, CatalogOperationEffect, WorkReference
from app.modules.books.evidence import BibliographicDataError, EditionEvidence, ExternalReference, normalize_isbns
from app.modules.books.identity import bibliographic_title, canonical_author_name, canonical_title_variants, duplicate_candidate
from app.modules.books.models import Author, CatalogSource, Edition, Work, WorkAuthor
from app.modules.library.models import LibraryEntry, Reading
from app.modules.users.models import User

logger = logging.getLogger(__name__)


class IncorporationConflict(ValueError):
    """Evidence or selection conflicts; caller must not silently retry as a new work."""


class EditionSelectionRequired(ValueError):
    pass


@dataclass(frozen=True)
class AdditionCommand:
    actor_user_id: uuid.UUID
    request_key: str
    internal_work_id: uuid.UUID | None = None
    edition_id: uuid.UUID | None = None
    external_reference: ExternalReference | None = None
    edition_selected: bool = False
    requested_reference: str | None = None

    def semantic_payload(self):
        if not self.request_key.strip() or len(self.request_key) > 200:
            raise ValueError("Invalid request key")
        if (self.internal_work_id is None) == (self.external_reference is None):
            raise ValueError("Choose one internal work or external publication reference")
        from app.core.config import get_settings
        if not get_settings().catalog_editionless_enabled and (not self.edition_selected or (self.internal_work_id and not self.edition_id)):
            raise EditionSelectionRequired("Editionless incorporation is not enabled")
        if self.internal_work_id and bool(self.edition_id) != self.edition_selected:
            raise ValueError("Edition selection must match the explicit edition UUID")
        if self.external_reference and self.edition_id:
            raise ValueError("External and internal edition selections cannot be mixed")
        return dict(internal_work_id=str(self.internal_work_id) if self.internal_work_id else None,
                    edition_id=str(self.edition_id) if self.edition_id else None,
                    external_reference=self.external_reference.as_dict() if self.external_reference else None,
                    edition_selected=self.edition_selected,
                    **({"requested_reference": self.requested_reference} if self.requested_reference else {}))


@dataclass(frozen=True)
class AdditionResult:
    operation_id: str
    incorporation_id: str
    physical_work_id: str
    canonical_work_id: str
    edition_id: str | None
    library_entry_id: str
    reading_id: str
    identity_status: str
    evidence_kind: str
    candidate_work_ids: tuple[str, ...]
    work_reused: bool
    edition_reused: bool


def _binding(db, reference):
    rows = db.scalars(select(WorkReference).where(
        WorkReference.provider == reference.provider, WorkReference.reference_type == reference.reference_type,
        WorkReference.external_id == reference.external_id)).all()
    binding = next((row for row in rows if row.verification_status in {"provisional", "confirmed"}), None)
    if any(row.verification_status in {"contradictory", "rejected"} for row in rows) and (
            binding is None or binding.verification_status != "confirmed"):
        raise IncorporationConflict("Recorded bibliographic contradiction requires review")
    return binding


def stored_publication(db, reference):
    """Exact persisted publication identity, not a search/cache match or metadata import."""
    feed_ref = ("openlibrary:" if reference.provider == "open-library" else "") + reference.external_id
    sources = db.scalars(select(CatalogSource).where(or_(
        (CatalogSource.provider == reference.provider) & (CatalogSource.external_id == reference.external_id),
        (CatalogSource.provider == "libria-feed") & (CatalogSource.external_id == feed_ref)))).all()
    if not sources:
        return None
    if any(source.validation_status != "validated" for source in sources) or len({source.edition_id for source in sources}) != 1:
        raise IncorporationConflict("Historical publication reference requires bibliographic review")
    return next((source for source in sources if source.provider == reference.provider), sources[0])


def _assert_compatible(db, edition, evidence):
    """Negative checks only: metadata agreement is never positive work identity."""
    old_ten, old_thirteen = normalize_isbns([v for v in (edition.isbn10, edition.isbn13) if v])
    if old_thirteen and evidence.isbn13 and old_thirteen != evidence.isbn13:
        raise IncorporationConflict("Publication reference contradicts stored ISBN")
    if not canonical_title_variants(edition.title) & canonical_title_variants(evidence.title):
        raise IncorporationConflict("Publication title contradicts stored edition")
    authors = db.scalars(select(Author.name).join(WorkAuthor, Author.id == WorkAuthor.author_id)
                         .where(WorkAuthor.work_id == edition.work_id)).all()
    offered = {canonical_author_name(n) for n in evidence.authors} - {""}
    known = {canonical_author_name(n) for n in authors} - {""}
    if offered and known and offered != known:
        raise IncorporationConflict("Publication authors contradict stored work")
    for old, incoming in ((edition.language, evidence.language), (edition.publisher_name, evidence.publisher)):
        if old and incoming and old != "und" and old.casefold().strip() != incoming.casefold().strip():
            raise IncorporationConflict("Publication language or publisher contradicts stored edition")
    if edition.page_count and evidence.page_count and edition.page_count != evidence.page_count:
        raise IncorporationConflict("Publication pages contradict stored edition")
    # Preserve source-level contradictions instead of trusting a contaminated Work.
    for source in db.scalars(select(CatalogSource).where(CatalogSource.edition_id == edition.id)):
        info = (source.payload or {}).get("volumeInfo") or {}
        names = {canonical_author_name(n) for n in info.get("authors") or []} - {""}
        if names and offered and names != offered:
            raise IncorporationConflict("Conflicting publication source authors")
        title = bibliographic_title(info)
        if title and not canonical_title_variants(title) & canonical_title_variants(evidence.title):
            raise IncorporationConflict("Conflicting publication source titles")


def _candidate_ids(db, work_id, title, names):
    authors = {}
    for key, name in db.execute(select(WorkAuthor.work_id, Author.name).join(Author, Author.id == WorkAuthor.author_id)):
        authors.setdefault(key, []).append(name)
    return tuple(sorted(str(w.id) for w in db.scalars(select(Work).where(Work.id != work_id))
                        if duplicate_candidate(title, names, w.title, authors.get(w.id, []))))


def _external_resolution(db, evidence, created, create_edition=True):
    reference = evidence.reference
    publication = _binding(db, reference)
    work_binding = _binding(db, evidence.verified_work) if evidence.verified_work else None
    if work_binding and work_binding.verification_status != "confirmed":
        raise IncorporationConflict("External work binding is not confirmed")
    source = db.scalar(select(CatalogSource).where(CatalogSource.provider == reference.provider,
                                                  CatalogSource.external_id == reference.external_id))
    if source and source.validation_status != "validated":
        raise IncorporationConflict("External publication source is not validated")
    clauses = ([Edition.isbn10 == evidence.isbn10] if evidence.isbn10 else []) + ([Edition.isbn13 == evidence.isbn13] if evidence.isbn13 else [])
    editions = {e.id: e for e in db.scalars(select(Edition).where(or_(*clauses)))} if clauses else {}
    if source:
        edition = db.get(Edition, source.edition_id)
        editions[edition.id] = edition
    # Legacy feed refs are exact provenance, never a title/author fallback.
    feed_ref = ("openlibrary:" if reference.provider == "open-library" else "") + reference.external_id
    feed = db.scalar(select(CatalogSource).where(CatalogSource.provider == "libria-feed", CatalogSource.external_id == feed_ref))
    if feed:
        edition = db.get(Edition, feed.edition_id)
        editions[edition.id] = edition
    if len(editions) > 1:
        raise IncorporationConflict("ISBNs and source reference identify different editions")
    edition = next(iter(editions.values()), None)
    known_ids = [b.work_id for b in (publication, work_binding) if b]
    if edition:
        _assert_compatible(db, edition, evidence)
        known_ids.append(edition.work_id)
    roots = {resolve_canonical_work(db, key).canonical_work_id for key in known_ids}
    if len(roots) > 1:
        raise IncorporationConflict("Publication and confirmed references identify different works")
    if not known_ids:
        from app.modules.books.catalog_identity import matching_work
        matched = matching_work(db, evidence.title, evidence.authors, reject_ambiguous=True)
        if matched:
            known_ids.append(matched.id)
    work_reused = bool(known_ids)
    if edition:
        work = db.get(Work, edition.work_id)
    elif known_ids:
        work = db.get(Work, known_ids[0])
        known_authors = {canonical_author_name(n) for n in db.scalars(
            select(Author.name).join(WorkAuthor, Author.id == WorkAuthor.author_id).where(WorkAuthor.work_id == work.id))} - {""}
        offered_authors = {canonical_author_name(n) for n in evidence.authors} - {""}
        if known_authors and offered_authors and known_authors != offered_authors:
            raise IncorporationConflict("Confirmed work reference contradicts known authors")
    else:
        info = evidence.snapshot().get("volumeInfo") or {}
        work = Work(title=evidence.title, identity_key=None,
                    description=info.get("description") if isinstance(info.get("description"), str) else None,
                    categories=[v for v in info.get("categories", []) if isinstance(v, str)] if isinstance(info.get("categories"), list) else None)
        db.add(work)
        db.flush()
        created.append(work)
        for position, name in enumerate(evidence.authors, 1):
            author = db.scalar(select(Author).where(func.lower(Author.name) == name.casefold()).order_by(Author.id))
            if author is None:
                author = Author(name=name)
                db.add(author)
                db.flush()
                created.append(author)
            if db.get(WorkAuthor, (work.id, author.id)) is None:
                link = WorkAuthor(work_id=work.id, author_id=author.id, position=position)
                db.add(link)
                created.append(link)
    edition_reused = edition is not None
    if edition is None and create_edition:
        info = evidence.snapshot().get("volumeInfo") or {}
        images = info.get("imageLinks") if isinstance(info.get("imageLinks"), dict) else {}
        edition = Edition(work_id=work.id, title=evidence.title, language=evidence.language or "und",
                          isbn10=evidence.isbn10, isbn13=evidence.isbn13, page_count=evidence.page_count,
                          publisher_name=evidence.publisher,
                          description=info.get("description") if isinstance(info.get("description"), str) else None,
                          publication_date=info.get("publishedDate") if isinstance(info.get("publishedDate"), str) else None,
                          format=info.get("printType") if isinstance(info.get("printType"), str) else None,
                          cover_url=images.get("thumbnail") if isinstance(images.get("thumbnail"), str) else None)
        db.add(edition)
        db.flush()
        created.append(edition)
    for provider, external_id in ((reference.provider, reference.external_id), ("libria-feed", feed_ref)):
        if not create_edition:
            continue
        existing = source if provider == reference.provider else feed
        if provider == "libria-feed" and existing is None and db.scalar(select(CatalogSource.id).where(
                CatalogSource.provider == "libria-feed", CatalogSource.edition_id == edition.id).limit(1)):
            # Keep one stable library alias; external provenance lives in provider sources.
            continue
        if existing is None:
            new_source = CatalogSource(edition_id=edition.id, provider=provider, external_id=external_id,
                                       fetched_at=evidence.fetched_at, detail_complete=provider != "libria-feed",
                                       payload=evidence.snapshot() if provider != "libria-feed" else None)
            db.add(new_source)
            created.append(new_source)
    isbn_reused = edition_reused and evidence.isbn13 and normalize_isbns(
        [v for v in (edition.isbn10, edition.isbn13) if v])[1] == evidence.isbn13
    legacy_reference = (source or feed) and publication is None
    confirmed = bool(work_binding or evidence.verified_work or isbn_reused or legacy_reference or
                     (publication and publication.verification_status == "confirmed"))
    kind = "verified_external_work" if evidence.verified_work else "publication_reference_or_isbn" if confirmed else "provisional_publication_reference"
    return work, edition if create_edition else None, publication, work_binding, confirmed, kind, work_reused, edition_reused


def incorporate_book(db: Session, command: AdditionCommand, evidence: EditionEvidence | None = None,
                     related_evidence: tuple[EditionEvidence, ...] = ()) -> AdditionResult:
    """Savepoint protects command even if caller catches an error; caller commits.

    Evidence must come from fetch_edition_evidence() before this call, outside the
    transaction's catalog locks. The opt-in public facade owns commit and retry.
    """
    semantic = command.semantic_payload()
    if command.external_reference and evidence and evidence.reference != command.external_reference:
        raise BibliographicDataError("Server evidence does not match the explicit selection")
    if evidence and not command.external_reference:
        raise BibliographicDataError("Unexpected external evidence for an internal selection")
    if evidence and normalize_isbns([v for v in (evidence.isbn10, evidence.isbn13) if v]) != (evidence.isbn10, evidence.isbn13):
        raise BibliographicDataError("Evidence ISBNs are not normalized")
    request_hash = hashlib.sha256(json.dumps(semantic, sort_keys=True).encode()).hexdigest()
    with db.begin_nested():
        lock_catalog_writes(db)
        actor = db.scalar(select(User).where(User.id == command.actor_user_id).with_for_update())
        if actor is None or actor.role == "libreria":
            raise PermissionError("This account cannot have a personal library")
        previous = db.scalar(select(CatalogOperation).where(
            CatalogOperation.actor_user_id == actor.id, CatalogOperation.operation_type == "library_add",
            CatalogOperation.request_key == command.request_key))
        if previous:
            if previous.request_hash != request_hash or "result" not in previous.context:
                raise IncorporationConflict("Idempotency key already used for another command")
            values = dict(previous.context["result"])
            values["candidate_work_ids"] = tuple(values["candidate_work_ids"])
            return AdditionResult(**values)
        stored = None
        if command.external_reference and evidence is None:
            lock_publication(db, command.external_reference.provider, command.external_reference.external_id, None)
            stored = stored_publication(db, command.external_reference)
            if stored is None:
                raise BibliographicDataError("Initial external incorporation requires server detail evidence")
        if evidence:
            lock_publication(db, evidence.reference.provider, evidence.reference.external_id, evidence.isbn13)
        created = []
        incorporated_editions = []
        publication = work_binding = None
        if evidence:
            work, edition, publication, work_binding, confirmed, kind, work_reused, edition_reused = _external_resolution(db, evidence, created, True)
            if not command.edition_selected:
                edition = None
        elif stored:
            edition = db.get(Edition, stored.edition_id)
            work = db.get(Work, edition.work_id)
            publication = _binding(db, command.external_reference)
            if publication and resolve_canonical_work(db, publication.work_id).canonical_work_id != resolve_canonical_work(db, work.id).canonical_work_id:
                raise IncorporationConflict("Historical source and reference binding identify different works")
            confirmed, kind, work_reused, edition_reused = True, "stored_publication_reference", True, True
            if not command.edition_selected:
                edition = None
        else:
            identity = resolve_canonical_work(db, command.internal_work_id)
            edition = db.get(Edition, command.edition_id) if command.edition_id else None
            if command.edition_selected and (edition is None or resolve_canonical_work(db, edition.work_id).canonical_work_id != identity.canonical_work_id):
                raise IncorporationConflict("Selected edition does not belong to the canonical work")
            work = db.get(Work, edition.work_id if edition else identity.canonical_work_id)
            confirmed, kind, work_reused, edition_reused = True, "internal_uuid", True, True
        from app.modules.books.identity import identity_matches
        related_title = evidence.title if evidence else work.title
        related_authors = evidence.authors if evidence else ()
        if related_evidence and not evidence:
            related_authors = db.scalars(select(Author.name).join(
                WorkAuthor, WorkAuthor.author_id == Author.id).where(WorkAuthor.work_id == work.id)).all()
        for related in related_evidence:
            if not identity_matches(related_title, related_authors, related.title, related.authors):
                continue
            lock_publication(db, related.reference.provider, related.reference.external_id, related.isbn13)
            related_created = []
            try:
                with db.begin_nested():
                    related_work, *_ = _external_resolution(db, related, related_created, True)
                    if resolve_canonical_work(db, related_work.id).canonical_work_id != resolve_canonical_work(db, work.id).canonical_work_id:
                        raise IncorporationConflict("Related edition identifies another stored work")
                    db.flush()
            except IncorporationConflict:
                logger.info("Skipped conflicting related catalog edition")
                continue
            created.extend(related_created)
            incorporated_editions.append(related)
        identity = resolve_canonical_work(db, work.id)
        entry = db.scalar(select(LibraryEntry).where(LibraryEntry.user_id == actor.id, LibraryEntry.work_id == work.id))
        from app.modules.books.canonical import enabled
        if enabled():
            active = db.scalars(select(LibraryEntry).where(LibraryEntry.user_id == actor.id,
                LibraryEntry.work_id.in_(canonical_members(db, work.id)), LibraryEntry.archived_at.is_(None))
                .order_by(LibraryEntry.created_at, LibraryEntry.id)).all()
            latest = db.scalar(select(Reading).where(Reading.library_entry_id.in_([e.id for e in active]))
                .order_by(Reading.created_at.desc(), Reading.id.desc())) if active else None
            if active:
                entry = next(e for e in active if latest and e.id == latest.library_entry_id) if latest else active[0]
                if edition and edition.work_id != entry.work_id:
                    raise IncorporationConflict("Selected edition requires an explicit physical membership transition")
                work = db.get(Work, entry.work_id)
        if entry is None:
            historical = db.scalar(select(LibraryEntry).where(LibraryEntry.user_id == actor.id,
                LibraryEntry.work_id.in_(canonical_members(db, work.id))).order_by(LibraryEntry.created_at, LibraryEntry.id).limit(1))
            if historical:
                from app.modules.books.canonical import enabled
                if not enabled() or (edition and edition.work_id != historical.work_id):
                    raise IncorporationConflict("Historical canonical membership requires an explicit edition transition")
                entry = historical
                work = db.get(Work, entry.work_id)
        if entry and entry.archived_at is not None:
            raise IncorporationConflict("Restoring an archived library requires an explicit future command")
        if entry is None:
            entry = LibraryEntry(user_id=actor.id, work_id=work.id)
            db.add(entry)
            db.flush()
            created.append(entry)
        reading = db.scalar(select(Reading).where(Reading.library_entry_id == entry.id).order_by(Reading.created_at.desc(), Reading.id.desc()))
        selected_id = edition.id if edition else None
        if reading and command.edition_selected and reading.edition_id != selected_id:
            raise IncorporationConflict("Existing reading has another edition; no selection was replaced")
        if reading is None:
            reading = Reading(library_entry_id=entry.id, work_id=work.id, edition_id=selected_id,
                              status="pending", current_page=0, total_pages=None)
            db.add(reading)
            db.flush()
            created.append(reading)
        candidates = _candidate_ids(db, work.id, evidence.title, evidence.authors) if evidence and not confirmed else ()
        result = AdditionResult(str(uuid.uuid4()), str(uuid.uuid4()), str(work.id), str(identity.canonical_work_id),
                                str(reading.edition_id) if reading.edition_id else None, str(entry.id), str(reading.id),
                                "confirmed" if confirmed else "candidate" if candidates else "insufficient",
                                kind, candidates, work_reused, edition_reused)
        operation = CatalogOperation(id=uuid.UUID(result.operation_id), actor_user_id=actor.id,
                                     operation_type="library_add", request_key=command.request_key, request_hash=request_hash,
                                     target_work_id=work.id, reason="Explicit library incorporation",
                                     evidence={**evidence.provenance(), "snapshot": evidence.snapshot(),
                                               "related_editions": [item.provenance() for item in incorporated_editions]} if evidence else
                                        {"stored_publication_reference": command.external_reference.as_dict(), "source_id": str(stored.id), "edition_id": str(stored.edition_id)} if stored else
                                        {"internal_uuid": str(command.internal_work_id)},
                                     context={"request": semantic, "result": asdict(result),
                                              "physical_work_id": str(work.id), "canonical_at_incorporation": str(identity.canonical_work_id),
                                              "canonical_path": [str(key) for key in identity.path],
                                              "redirect_operations": [str(key) for key in identity.operation_ids]})
        if incorporated_editions:
            operation.evidence = {**operation.evidence, "related_editions": [
                {**item.provenance(), "snapshot": item.snapshot()} for item in incorporated_editions]}
        db.add(operation)
        db.flush()
        if stored and publication is None:
            reference = command.external_reference
            publication = WorkReference(work_id=work.id, provider=reference.provider, reference_type=reference.reference_type,
                external_id=reference.external_id, verification_status="provisional", evidence=operation.evidence, operation_id=operation.id)
            db.add(publication)
            db.flush()
            created.append(publication)
        if evidence:
            for reference, binding, is_confirmed in ((evidence.reference, publication, bool(evidence.verified_work)),
                                                       (evidence.verified_work, work_binding, True)):
                if reference is None or binding:
                    continue
                binding = WorkReference(work_id=work.id, provider=reference.provider, reference_type=reference.reference_type,
                                        external_id=reference.external_id, verification_status="confirmed" if is_confirmed else "provisional",
                                        evidence=evidence.provenance(), verified_by="open-library-detail" if is_confirmed else None,
                                        verified_at=evidence.fetched_at if is_confirmed else None, operation_id=operation.id)
                db.add(binding)
                db.flush()
                created.append(binding)
                if reference == evidence.reference:
                    publication = binding
        receipt = CatalogIncorporation(id=uuid.UUID(result.incorporation_id), operation_id=operation.id,
                                       actor_user_id=actor.id, origin="library", work_id=work.id, edition_id=selected_id,
                                       edition_selected=command.edition_selected, library_entry_id=entry.id,
                                       reference_id=publication.id if publication and publication.work_id == work.id else None,
                                       requested_reference=semantic)
        db.add(receipt)
        created.append(receipt)
        db.flush()
        for ordinal, entity in enumerate(created, 1):
            image = {column.key: getattr(entity, column.key) for column in inspect(type(entity)).columns}
            image = json.loads(json.dumps(image, default=str))
            entity_id = getattr(entity, "id", None) or entity.work_id
            db.add(CatalogOperationEffect(operation_id=operation.id, ordinal=ordinal,
                                          entity_table=entity.__table__.fullname, entity_id=entity_id,
                                          before_state=None, after_state=image))
        db.flush()
        return result


@dataclass(frozen=True)
class ImportResult:
    operation_id: str
    incorporation_id: str
    physical_work_id: str
    canonical_work_id: str
    edition_id: str


def import_book(db, actor_user_id, request_key, evidence, reason):
    """Authorized administrative entry point; same identity resolver and graph lock."""
    from app.modules.users.identity_models import AccountPermission
    if not request_key.strip() or len(request_key) > 200 or not reason.strip():
        raise ValueError("An import needs a request key and reason")
    if normalize_isbns([v for v in (evidence.isbn10, evidence.isbn13) if v]) != (evidence.isbn10, evidence.isbn13):
        raise BibliographicDataError("Evidence ISBNs are not normalized")
    semantic = {"reference": evidence.reference.as_dict(), "reason": reason}
    request_hash = hashlib.sha256(json.dumps(semantic, sort_keys=True).encode()).hexdigest()
    with db.begin_nested():
        lock_catalog_writes(db)
        actor = db.scalar(select(User).where(User.id == actor_user_id).with_for_update())
        if actor is None or db.get(AccountPermission, (actor_user_id, "admin")) is None:
            raise PermissionError("Administrative account permission required")
        previous = db.scalar(select(CatalogOperation).where(CatalogOperation.actor_user_id == actor_user_id,
            CatalogOperation.operation_type == "admin_import", CatalogOperation.request_key == request_key))
        if previous:
            if previous.request_hash != request_hash:
                raise IncorporationConflict("Idempotency key already used for another import")
            return ImportResult(**previous.context["result"])
        lock_publication(db, evidence.reference.provider, evidence.reference.external_id, evidence.isbn13)
        created = []
        work, edition, publication, work_binding, confirmed, kind, _, _ = _external_resolution(db, evidence, created)
        identity = resolve_canonical_work(db, work.id)
        result = ImportResult(str(uuid.uuid4()), str(uuid.uuid4()), str(work.id), str(identity.canonical_work_id), str(edition.id))
        operation = CatalogOperation(id=uuid.UUID(result.operation_id), actor_user_id=actor_user_id,
            operation_type="admin_import", request_key=request_key, request_hash=request_hash,
            target_work_id=work.id, reason=reason, evidence={**evidence.provenance(), "snapshot": evidence.snapshot()},
            context={"request": semantic, "result": asdict(result), "evidence_kind": kind,
                     "canonical_path": [str(key) for key in identity.path],
                     "redirect_operations": [str(key) for key in identity.operation_ids]})
        db.add(operation)
        db.flush()
        for reference, binding, verified in ((evidence.reference, publication, bool(evidence.verified_work)),
                                             (evidence.verified_work, work_binding, True)):
            if reference is None or binding:
                continue
            binding = WorkReference(work_id=work.id, provider=reference.provider, reference_type=reference.reference_type,
                external_id=reference.external_id, verification_status="confirmed" if verified else "provisional",
                evidence=evidence.provenance(), verified_by="open-library-detail" if verified else None,
                verified_at=evidence.fetched_at if verified else None, operation_id=operation.id)
            db.add(binding)
            db.flush()
            created.append(binding)
            if reference == evidence.reference:
                publication = binding
        receipt = CatalogIncorporation(id=uuid.UUID(result.incorporation_id), operation_id=operation.id,
            actor_user_id=actor_user_id, origin="admin_import", work_id=work.id, edition_id=edition.id,
            edition_selected=True, reference_id=publication.id if publication and publication.work_id == work.id else None,
            requested_reference=semantic)
        db.add(receipt)
        created.append(receipt)
        db.flush()
        for ordinal, entity in enumerate(created, 1):
            image = {column.key: getattr(entity, column.key) for column in inspect(type(entity)).columns}
            db.add(CatalogOperationEffect(operation_id=operation.id, ordinal=ordinal,
                entity_table=entity.__table__.fullname, entity_id=getattr(entity, "id", None) or entity.work_id,
                before_state=None, after_state=json.loads(json.dumps(image, default=str))))
        db.flush()
        return result
