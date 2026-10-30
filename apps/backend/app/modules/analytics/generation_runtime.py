"""Expose configuration readiness without starting workers or calling a provider."""


def generation_runtime(settings):
    allowed = settings.gemini_paid_service_confirmed or (
        settings.gemini_free_test_mode and settings.app_env in {'development', 'test'})
    return {
        'generation_enabled': bool(settings.gemini_worker_enabled and allowed),
        'generation_blocked_reason': ('worker_disabled' if not settings.gemini_worker_enabled
                                      else 'activation_required' if not allowed else None),
    }
