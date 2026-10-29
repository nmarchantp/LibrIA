"""Public boundary: no client metadata is bibliographic evidence; no HTTP under locks."""
import hashlib
import uuid

from fastapi import HTTPException
from sqlalchemy import select

from app.modules.books.evidence import BibliographicDataError, ExternalReference, evidence_from_snapshot, fetch_edition_evidence
from app.modules.books.models import CatalogSource, Edition, Work
from app.modules.books.policy import execute_catalog_command, provider_budget
from app.modules.books.resolution import AdditionCommand, EditionSelectionRequired, IncorporationConflict, incorporate_book, import_book, stored_publication
from app.modules.books.canonical import CanonicalIdentityError


def external_reference(value):
    if value.startswith("openlibrary:"):
        return ExternalReference("open-library", "edition", value)
    return ExternalReference("google-books", "volume", value.removeprefix("googlebooks:"))


def _command(db, data, actor_id, key):
    if data.external_reference:
        reference = ExternalReference(**data.external_reference.model_dump())
        from app.core.config import get_settings
        if data.edition_id or (not data.edition_selected and not get_settings().catalog_editionless_enabled):
            raise EditionSelectionRequired("Selecciona explícitamente una edición.")
        return AdditionCommand(actor_id, key, external_reference=reference, edition_selected=data.edition_selected)
    try:
        internal_id = uuid.UUID(data.book_ref)
    except ValueError:
        internal_id = None
    if internal_id:
        work, edition = db.get(Work, internal_id), db.get(Edition, internal_id)
        if work is None and edition:
            return AdditionCommand(actor_id, key, internal_work_id=edition.work_id, edition_id=edition.id, edition_selected=True)
        if work is None:
            raise CanonicalIdentityError("UUID de obra desconocido")
        return AdditionCommand(actor_id, key, internal_work_id=work.id, edition_id=data.edition_id,
                               edition_selected=bool(data.edition_id))
    # Stable legacy feed refs (including native default-admin refs) remain usable,
    # but an unknown manual ref must never fall back to a title-only import.
    source = db.scalar(select(CatalogSource).where(CatalogSource.provider == "libria-feed",
                                                  CatalogSource.external_id == data.book_ref))
    if source and (":" in data.book_ref and not data.book_ref.startswith(("openlibrary:", "googlebooks:"))):
        edition = db.get(Edition, source.edition_id)
        return AdditionCommand(actor_id, key, internal_work_id=edition.work_id,
                               edition_id=data.edition_id or edition.id, edition_selected=True, requested_reference=data.book_ref)
    return AdditionCommand(actor_id, key, external_reference=external_reference(data.book_ref), edition_selected=True)


def server_evidence(db, reference):
    source = db.scalar(select(CatalogSource).where(CatalogSource.provider == reference.provider,
        CatalogSource.external_id == reference.external_id, CatalogSource.validation_status == "validated"))
    snapshot = source.payload if source else None
    fetched_at = source.fetched_at if source else None
    db.rollback()  # all previous activity in this request is read-only
    if snapshot:
        # A persisted publication identity is sufficient; do not infer a work link
        # from an old search payload, even if it contains openLibrary.workKey.
        return evidence_from_snapshot(reference, snapshot, fetched_at=fetched_at)
    with provider_budget():
        return fetch_edition_evidence(reference)


def public_addition(db, data, actor_id, request_key=None):
    # Compatibility clients without a header get a deterministic reference/selection key.
    fallback = f"{data.book_ref}:{data.edition_id}:{data.external_reference}:{data.edition_selected}"
    key = request_key or "legacy-" + hashlib.sha256(fallback.encode()).hexdigest()
    try:
        command = _command(db, data, actor_id, key)
        command.semantic_payload()
        db.rollback()
        from app.modules.books.catalog_models import CatalogOperation, WorkReference
        previous = db.scalar(select(CatalogOperation.id).where(CatalogOperation.actor_user_id == actor_id,
            CatalogOperation.operation_type == "library_add", CatalogOperation.request_key == key))
        recovery = None
        if command.external_reference:
            # A replay has no dependency on a currently available provider.
            stored = stored_publication(db, command.external_reference) if not previous else None
            db.rollback()
            evidence = None if previous or stored else server_evidence(db, command.external_reference)
        else:
            evidence = None
            # Earlier editionless saves retained the provider reference but no
            # edition/source. Recover those publications without another Work.
            if not previous:
                from app.modules.books.canonical import canonical_members
                members = canonical_members(db, command.internal_work_id)
                has_edition = db.scalar(select(Edition.id).where(Edition.work_id.in_(members)).limit(1))
                binding = None if has_edition else db.scalar(select(WorkReference).where(
                    WorkReference.work_id.in_(members), WorkReference.reference_type.in_(["volume", "edition"]),
                    WorkReference.verification_status.in_(["provisional", "confirmed"])).order_by(WorkReference.id).limit(1))
                if binding:
                    reference = ExternalReference(binding.provider, binding.reference_type, binding.external_id)
                    try:
                        recovery = server_evidence(db, reference)
                    except (HTTPException, BibliographicDataError):
                        pass
            db.rollback()
        from app.modules.books.edition_discovery import discover_editions
        related = ()
        if evidence:
            related = discover_editions(evidence)
        elif recovery:
            related = (recovery, *discover_editions(recovery))
        return execute_catalog_command(db, lambda: incorporate_book(db, command, evidence, related))
    except PermissionError as error:
        db.rollback()
        raise HTTPException(403, str(error)) from None
    except IncorporationConflict as error:
        db.rollback()
        raise HTTPException(409, detail={"code": "bibliographic_conflict", "message": str(error)}) from None
    except CanonicalIdentityError as error:
        db.rollback()
        raise HTTPException(404, str(error)) from None
    except (BibliographicDataError, EditionSelectionRequired, ValueError) as error:
        db.rollback()
        raise HTTPException(422, str(error)) from None
    except Exception:
        db.rollback()
        raise


def public_import(db, actor_id, reference, request_key, reason):
    try:
        # Permission is checked before network access and again inside the service.
        from app.modules.users.identity_models import AccountPermission
        if db.get(AccountPermission, (actor_id, "admin")) is None:
            raise PermissionError("Se requiere una cuenta administradora")
        evidence = server_evidence(db, reference)
        return execute_catalog_command(db, lambda: import_book(db, actor_id, request_key, evidence, reason))
    except PermissionError as error:
        db.rollback()
        raise HTTPException(403, str(error)) from None
    except IncorporationConflict as error:
        db.rollback()
        raise HTTPException(409, detail={"code": "bibliographic_conflict", "message": str(error)}) from None
    except (BibliographicDataError, ValueError) as error:
        db.rollback()
        raise HTTPException(422, str(error)) from None
    except Exception:
        db.rollback()
        raise
