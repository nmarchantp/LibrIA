"""Read model access without generating text or exposing keys/provider messages."""
import json
import re
import httpx
from app.core.config import get_settings


def main():
    settings = get_settings()
    key = settings.gemini_api_key.get_secret_value()
    if not key:
        print(json.dumps({'key_present': False}))
        return 1
    try:
        response = httpx.get('https://generativelanguage.googleapis.com/v1beta/models/' + settings.gemini_model,
                             headers={'x-goog-api-key': key}, timeout=25)
        data = response.json()
    except (httpx.HTTPError, ValueError):
        print(json.dumps({'status': 'transport_error'}))
        return 1
    error = data.get('error') or {}
    message = str(error.get('message') or '').lower()
    reasons = [item.get('reason') for item in error.get('details', []) if isinstance(item, dict)]
    safe_reasons = [reason for reason in reasons if isinstance(reason, str) and re.fullmatch(r'[A-Z_]{1,80}', reason)]
    print(json.dumps({'http_status': response.status_code, 'model': settings.gemini_model,
                      'model_access': response.status_code == 200, 'reasons': safe_reasons,
                      'mentions_expired': 'expired' in message, 'mentions_leaked': 'leaked' in message,
                      'mentions_disabled': 'disabled' in message, 'mentions_restriction': 'restrict' in message,
                      'mentions_invalid_key': 'api key not valid' in message or 'invalid api key' in message}))
    return 0 if response.status_code == 200 else 1


if __name__ == '__main__':
    raise SystemExit(main())
