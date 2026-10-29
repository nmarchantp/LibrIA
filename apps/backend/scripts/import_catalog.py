"""Explicit admin import CLI. Search selects a batch; identity belongs to resolution.py."""
import argparse
import hashlib
import uuid

from app.main import app as _application  # noqa: F401, register ORM metadata
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.books.evidence import ExternalReference
from app.modules.books.facade import public_import, external_reference
from app.modules.books.google_books import google_request
from app.modules.books.policy import provider_budget
from app.modules.users.identity_models import AccountPermission


def main(default_queries=()):
    parser = argparse.ArgumentParser(description="Import selected publications with an authorized administrator account")
    parser.add_argument("--admin-user-id", required=True, type=uuid.UUID)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--request-prefix", required=True, help="Stable batch key; reuse for retries")
    parser.add_argument("--reference", action="append", default=[], help="Google ID or openlibrary:OL...M")
    parser.add_argument("--query", action="append", default=[], help="Explicitly authorizes all returned Spanish Google publications")
    parser.add_argument("--refresh-known", action="store_true", help="Use only queries previously cached by this application")
    args = parser.parse_args()
    if not get_settings().catalog_discovery_enabled:
        parser.error("The discovery/incorporation bundle is disabled; obtain rollout authorization first")
    with SessionLocal() as db:
        if db.get(AccountPermission, (args.admin_user_id, "admin")) is None:
            raise PermissionError("An administrator account permission is required")
        queries = list(args.query or default_queries)
        if args.refresh_known:
            from app.modules.books.models import CatalogQuery
            from sqlalchemy import select
            for key in db.scalars(select(CatalogQuery.query)):
                if key.startswith("discovery-v1:"):
                    parts = key.split(":")
                    queries.append(":".join(parts[2:-2]))
    references = [external_reference(value) for value in args.reference]
    for query in dict.fromkeys(queries):
        with provider_budget():
            result = google_request(query=query)
        for item in result.get("items") or []:
            if isinstance(item, dict) and isinstance(item.get("id"), str) and (item.get("volumeInfo") or {}).get("language") == "es":
                references.append(ExternalReference("google-books", "volume", item["id"]))
    if not references:
        parser.error("Provide --reference, --query or an authorized default batch")
    imported = 0
    for reference in dict.fromkeys(references):
        key = "batch-" + hashlib.sha256((args.request_prefix + repr(reference)).encode()).hexdigest()
        with SessionLocal() as db:
            public_import(db, args.admin_user_id, reference, key, args.reason)
        imported += 1
    print({"imported_publications": imported, "reason": args.reason})


if __name__ == "__main__":
    main()
