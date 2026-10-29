"""Server-side publication snapshots, fetched before any catalog write locks.

These helpers never access a database. Snapshots are internal service inputs,
not HTTP schemas; a client cannot supply its own verification flag.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import hashlib
import re
from urllib.parse import quote

from app.modules.books import open_library
from app.modules.books.google_books import google_request
from app.modules.books.identity import bibliographic_title


class BibliographicDataError(ValueError):
    pass


@dataclass(frozen=True)
class ExternalReference:
    provider: str
    reference_type: str
    external_id: str

    def __post_init__(self):
        value = self.external_id.strip()
        if self.provider == "google-books" and self.reference_type == "volume":
            valid = re.fullmatch(r"[A-Za-z0-9_-]{1,200}", value)
        elif self.provider == "open-library" and self.reference_type in {"work", "edition"}:
            value = open_library.key(value.removeprefix("openlibrary:"), "W" if self.reference_type == "work" else "M")
            valid = value is not None
        else:
            valid = False
        if not valid:
            raise BibliographicDataError("Invalid provider reference")
        object.__setattr__(self, "external_id", value)

    def as_dict(self):
        return dict(provider=self.provider, reference_type=self.reference_type, external_id=self.external_id)


def normalize_isbns(values) -> tuple[str | None, str | None]:
    """Validate checksum, book prefix, and ISBN-10/13 equivalence before reuse."""
    publications = set()
    for raw in values:
        value = re.sub(r"[\s-]", "", str(raw)).upper()
        if re.fullmatch(r"[0-9]{9}[0-9X]", value):
            if sum((10-i) * (10 if c == "X" else int(c)) for i, c in enumerate(value)) % 11:
                raise BibliographicDataError("Invalid ISBN-10 checksum")
            base = "978" + value[:9]
            value = base + str(-sum(int(c)*(1 if i % 2 == 0 else 3) for i, c in enumerate(base)) % 10)
        elif re.fullmatch(r"97[89][0-9]{10}", value):
            if sum(int(c)*(1 if i % 2 == 0 else 3) for i, c in enumerate(value)) % 10:
                raise BibliographicDataError("Invalid ISBN-13 checksum")
        else:
            raise BibliographicDataError("Invalid book ISBN")
        publications.add(value)
    if len(publications) > 1:
        raise BibliographicDataError("Contradictory publication ISBNs")
    if not publications:
        return None, None
    thirteen = publications.pop()
    ten = None
    if thirteen.startswith("978"):
        base = thirteen[3:12]
        digit = -sum((10-i)*int(c) for i, c in enumerate(base)) % 11
        ten = base + ("X" if digit == 10 else str(digit))
    return ten, thirteen


@dataclass(frozen=True)
class EditionEvidence:
    reference: ExternalReference
    title: str
    authors: tuple[str, ...]
    isbn10: str | None
    isbn13: str | None
    language: str | None
    page_count: int | None
    publisher: str | None
    snapshot_json: str
    fetched_at: datetime
    verified_work: ExternalReference | None = None

    def snapshot(self):
        return json.loads(self.snapshot_json)

    def provenance(self):
        return dict(provider=self.reference.provider, reference=self.reference.as_dict(),
                    fetched_at=self.fetched_at.isoformat(), transport="server_detail",
                    snapshot_sha256=hashlib.sha256(self.snapshot_json.encode()).hexdigest(),
                    work_reference=self.verified_work.as_dict() if self.verified_work else None)


def fetch_edition_evidence(reference: ExternalReference) -> EditionEvidence:
    """Only detail endpoints attest source identity; never search/cache client JSON."""
    verified_work = None
    if reference.provider == "google-books":
        item = google_request("/" + quote(reference.external_id, safe=""))
        if not isinstance(item, dict) or item.get("id") != reference.external_id:
            raise BibliographicDataError("Provider returned a different volume")
    elif reference.reference_type == "edition":
        # Existing detail() verifies edition.works membership and fetches work data.
        item = open_library.detail(reference.external_id)
        if not isinstance(item, dict) or not isinstance(item.get("openLibrary"), dict) or item["openLibrary"].get("editionKey") != reference.external_id:
            raise BibliographicDataError("Provider returned a different edition")
        work_key = item.get("openLibrary", {}).get("workKey")
        if work_key:
            verified_work = ExternalReference("open-library", "work", work_key)
    else:
        raise BibliographicDataError("An explicit publication selection is required")
    return evidence_from_snapshot(reference, item, verified_work=verified_work)


def evidence_from_snapshot(reference, item, *, verified_work=None, fetched_at=None):
    """Internal parser for server-owned detail or persisted source snapshots, never client JSON."""
    if not isinstance(item, dict):
        raise BibliographicDataError("Invalid publication snapshot")
    info = item.get("volumeInfo")
    if not isinstance(info, dict) or not isinstance(info.get("title"), str) or not info["title"].strip():
        raise BibliographicDataError("Publication title is missing")
    title = bibliographic_title(info).strip()
    if info.get("authors") is not None and not isinstance(info["authors"], list):
        raise BibliographicDataError("Publication authors must be a list")
    authors = tuple(name.strip() for name in (info.get("authors") or []) if isinstance(name, str) and name.strip())
    identifiers = info.get("industryIdentifiers") or []
    if not isinstance(identifiers, list):
        raise BibliographicDataError("Publication identifiers must be a list")
    ten, thirteen = normalize_isbns([v.get("identifier") for v in identifiers
                                   if isinstance(v, dict) and v.get("type") in {"ISBN_10", "ISBN_13"}])
    pages = info.get("pageCount")
    pages = pages if type(pages) is int and pages > 0 else None
    language = info.get("language") if isinstance(info.get("language"), str) else None
    publisher = info.get("publisher") if isinstance(info.get("publisher"), str) else None
    return EditionEvidence(reference, title, authors, ten, thirteen, language, pages, publisher,
                           json.dumps(item, sort_keys=True, ensure_ascii=False), fetched_at or datetime.now(timezone.utc), verified_work)
