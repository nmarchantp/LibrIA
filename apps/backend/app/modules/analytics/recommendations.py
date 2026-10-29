"""Shared catalog metadata plus disabled synchronous compatibility calls."""
from fastapi import HTTPException

VERSION = "reader-books-v4-analytics-social"
BATCH_SIZE = 4


def metadata(edition, source):
    info = (source.payload or {}).get("volumeInfo", {}) if source else {}
    return {"id": source.external_id if source else str(edition.id), "title": edition.title[:200],
            "description": str(info.get("description") or "")[:800],
            "authors": [author[:100] for author in info.get("authors", []) if isinstance(author, str)][:5],
            "categories": [category[:100] for category in info.get("categories", []) if isinstance(category, str)][:5],
            "language": edition.language, "pages": edition.page_count}


def validate_selection(content, candidates):
    if not isinstance(content, dict) or set(content) != {"recommendations"}:
        raise ValueError("Invalid recommendation object")
    selected = content["recommendations"]
    if not isinstance(selected, list) or not 1 <= len(selected) <= min(BATCH_SIZE, len(candidates)):
        raise ValueError("Invalid recommendation count")
    lookup = {item["metadata"]["id"]: item for item in candidates}
    seen, result = set(), []
    for selection in selected:
        if not isinstance(selection, dict) or set(selection) != {"id", "criterion"}:
            raise ValueError("Invalid recommendation fields")
        book = lookup.get(selection["id"])
        if not book or selection["id"] in seen or selection["criterion"] not in book["reasons"]:
            raise ValueError("Unsupported book or preference")
        seen.add(selection["id"])
        result.append({"volume": book["volume"], "reason": book["reasons"][selection["criterion"]]})
    return result


def _disabled():
    raise HTTPException(410, "La generación síncrona heredada está desactivada; usa la cola Gemini persistente")


def prepare(*_args, **_kwargs):
    return _disabled()


def generate(*_args, **_kwargs):
    return _disabled()


def recommendations(*_args, **_kwargs):
    return _disabled()
