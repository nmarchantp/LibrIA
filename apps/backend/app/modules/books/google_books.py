"""Bounded Google Books requests; never log keys, URLs or search text."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging
import time

import httpx
from fastapi import HTTPException

from app.core.config import get_settings

logger = logging.getLogger(__name__)
MESSAGES = {
    "quota": "Google Books alcanzó su límite de consultas. Inténtalo más tarde.",
    "permissions": "Google Books rechazó el acceso. Debe revisarse la configuración del servicio.",
    "invalid_query": "Google Books no pudo procesar esta búsqueda. Revisa el título, autor o ISBN.",
    "connection": "No se pudo conectar con Google Books. Inténtalo nuevamente.",
    "unavailable": "Google Books no está disponible en este momento.",
    "invalid_response": "Google Books devolvió una respuesta incompleta o inválida.",
}


def valid_volume(item):
    return (isinstance(item, dict) and isinstance(item.get("id"), str) and bool(item["id"].strip())
            and isinstance(item.get("volumeInfo"), dict)
            and isinstance(item["volumeInfo"].get("title"), str)
            and bool(item["volumeInfo"]["title"].strip()))


def safe_volume_info(item):
    info = dict(item.get("volumeInfo") or {})
    for field in ("authors", "categories"):
        values = info.get(field)
        info[field] = [v for v in values if isinstance(v, str) and v.strip()] if isinstance(values, list) else []
    ids = info.get("industryIdentifiers")
    info["industryIdentifiers"] = [v for v in ids if isinstance(v, dict)] if isinstance(ids, list) else []
    images = info.get("imageLinks")
    info["imageLinks"] = {k: v for k, v in images.items() if isinstance(v, str)} if isinstance(images, dict) else {}
    for field in ("description", "publisher", "publishedDate", "language", "printType"):
        if not isinstance(info.get(field), str):
            info[field] = None
    return info


def retry_after(response):
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0, float(value))
    except ValueError:
        try:
            return max(0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def google_request(path="", query=None, *, start_index=0, pages=1):
    params = {"projection": "full"}
    if query is not None:
        params.update(q=query, maxResults=40, langRestrict="es")
    key = get_settings().google_books_api_key
    if key:
        params["key"] = key
    started = time.monotonic()
    deadline = started + 15
    waited = 0
    unique = {}
    partial = False
    next_start = start_index
    has_more = False
    error_detail = None
    with httpx.Client(timeout=10) as client:
        for page_index in range(min(max(pages, 1), 3) if query is not None else 1):
            start = start_index + page_index * 40
            page_params = {**params, "startIndex": start} if query is not None else params
            page = None
            for attempt in range(3):
                status = None
                delay = None
                transient = False
                code = "unavailable"
                try:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise httpx.TimeoutException("Request budget exhausted")
                    response = client.get("https://www.googleapis.com/books/v1/volumes" + path,
                        params=page_params, timeout=httpx.Timeout(min(10, remaining), connect=min(3, remaining)))
                    status = response.status_code
                    if status == 404 and query is None:
                        raise HTTPException(404, "Libro no encontrado")
                    transient = status in {500, 502, 503, 504}
                    delay = retry_after(response)
                    if status == 429:
                        code = "quota"
                        transient = delay is not None
                    elif status == 403:
                        code = "permissions"
                        try:
                            reasons = [v.get("reason") for v in response.json().get("error", {}).get("errors", []) if isinstance(v, dict)]
                            if any(v in {"dailyLimitExceeded", "quotaExceeded", "rateLimitExceeded", "userRateLimitExceeded"} for v in reasons):
                                code = "quota"
                        except (ValueError, AttributeError, TypeError):
                            pass
                    elif status == 400:
                        code = "invalid_query"
                    response.raise_for_status()
                    page = response.json()
                    if not isinstance(page, dict):
                        raise ValueError("Invalid response")
                    break
                except (httpx.HTTPError, ValueError) as error:
                    page = None
                    if isinstance(error, httpx.RequestError):
                        code = "connection"
                        transient = True
                    elif isinstance(error, ValueError):
                        code = "invalid_response"
                    error_detail = {"code": code, "message": MESSAGES[code], "provider_status": status}
                    if delay is not None:
                        error_detail["retry_after"] = min(86400, max(0, delay))
                    logger.warning("Google Books failure code=%s status=%s attempt=%s page=%s elapsed_ms=%s",
                        code, status, attempt + 1, page_index + 1, round((time.monotonic() - started) * 1000))
                    wait = max(0.5 * (2 ** attempt), delay or 0)
                    # Never retry sooner than Retry-After. Large values are left
                    # to the caller instead of tying up a web worker indefinitely.
                    if not transient or attempt == 2 or waited + wait > 3 or time.monotonic() + wait >= deadline:
                        break
                    time.sleep(wait)
                    waited += wait
            if page is None:
                if query is None or not unique:
                    raise HTTPException(502, error_detail or {"code": "unavailable", "message": MESSAGES["unavailable"]})
                partial = True
                has_more = True
                next_start = start
                break
            if query is None:
                return page
            raw_items = page.get("items") or []
            if not isinstance(raw_items, list):
                raw_items = []
                partial = True
            for item in raw_items:
                if valid_volume(item):
                    unique[item["id"]] = item
                else:
                    partial = True
            next_start = start + 40
            has_more = len(raw_items) == 40
            if not has_more:
                break
    result = {"totalItems": len(unique), "items": list(unique.values()), "has_more": has_more,
              "next_start_index": next_start if has_more else None}
    if partial:
        result.update(partial=True, error_code=(error_detail or {}).get("code", "invalid_response"),
                      warning=(error_detail or {}).get("message", MESSAGES["invalid_response"]))
        if error_detail and "retry_after" in error_detail:
            result["retry_after"] = error_detail["retry_after"]
    return result
