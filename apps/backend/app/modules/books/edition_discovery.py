"""Collect server-verified editions before opening the catalog transaction."""
from fastapi import HTTPException

from app.modules.books.evidence import BibliographicDataError, ExternalReference, fetch_edition_evidence
from app.modules.books.google_books import google_request
from app.modules.books.identity import bibliographic_title, identity_matches
from app.modules.books.policy import provider_budget


def discover_editions(evidence):
    if not evidence.authors:
        return ()
    related = []
    seen = {(evidence.reference.provider, evidence.reference.external_id)}
    # The provider exposes a paged, incomplete catalog. Bound remote I/O; never
    # claim that an unavailable edition was imported or trust search as detail.
    with provider_budget():
        try:
            query = 'intitle:"' + evidence.title.replace('"', ' ') + '" inauthor:"' + evidence.authors[0].replace('"', ' ') + '"'
            start = 0
            while True:
                result = google_request(query=query, start_index=start)
                for item in result.get("items", []):
                    info = item.get("volumeInfo") or {}
                    key = ("google-books", item.get("id"))
                    if key in seen or not identity_matches(evidence.title, evidence.authors,
                            bibliographic_title(info), info.get("authors") or []):
                        continue
                    seen.add(key)
                    try:
                        candidate = fetch_edition_evidence(ExternalReference("google-books", "volume", item["id"]))
                    except BibliographicDataError:
                        continue
                    if candidate.isbn13 and identity_matches(evidence.title, evidence.authors, candidate.title, candidate.authors):
                        related.append(candidate)
                if not result.get("has_more") or result.get("partial"):
                    break
                start = result["next_start_index"]
        except HTTPException:
            # Saving the requested book must survive enrichment quota/timeouts.
            pass
    return tuple(related)
