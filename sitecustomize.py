"""
sitecustomize.py — Python startup customization loaded automatically by the
interpreter before user code runs.

HOTFIX: Suppress deprecated bidRecommendations 429s from the Amazon Ads API
while keeping per-keyword bid-recommendation calls functional.

When Amazon returns HTTP 429 with "deprecated resource" for the bulk
bidRecommendations endpoint, this module patches requests.Session.send so
that the response status is converted to 404.  The SuggestedBidOptimizer
then treats the affected keywords as "no recommendation" (no-reco) instead
of raising a DeprecatedEndpointError that would abort the entire batch.

Usage from SuggestedBidOptimizer:
    import sitecustomize as _sc
    _sc.log_hotfix_active()   # logs "HOTFIX active: …" via the sitecustomize logger
"""

import logging

_logger = logging.getLogger("sitecustomize")

# True once the requests patch has been successfully applied.
HOTFIX_ACTIVE: bool = False

# Avoid repeating "detected" log messages on every patched response.
_detection_logged: bool = False


def _should_convert_to_no_reco(response_status: int, url: str, body: str) -> bool:
    """Return True when the response is a deprecated-resource 429 that should
    be treated as no-reco (404) by the SuggestedBidOptimizer.

    Exposed as a standalone helper so it can be unit-tested independently of
    the requests.Session monkey-patch.
    """
    return (
        response_status == 429
        and "bidRecommendations" in url
        and "deprecated" in body.lower()
    )


def _apply_hotfix() -> None:
    """Patch requests.Session.send to suppress deprecated bidRecommendations 429s."""
    global HOTFIX_ACTIVE
    try:
        import requests as _requests

        _original_send = _requests.Session.send

        def _patched_send(self, request, **kwargs):  # type: ignore[override]
            response = _original_send(self, request, **kwargs)

            if _should_convert_to_no_reco(
                response.status_code,
                request.url or "",
                response.text or "",
            ):
                global _detection_logged
                if not _detection_logged:
                    _detection_logged = True
                    _logger.warning(
                        "HOTFIX: detected deprecated bidRecommendations 429s; "
                        "treating as no-reco for affected keyword IDs."
                    )
                # Convert to 404 so the optimizer treats it as no-reco rather
                # than raising DeprecatedEndpointError.
                response.status_code = 404

            return response

        _requests.Session.send = _patched_send  # type: ignore[method-assign]
        HOTFIX_ACTIVE = True
    except Exception:
        # Never crash the interpreter startup.
        pass


def log_hotfix_active() -> None:
    """Log "HOTFIX active" banner.  Called by SuggestedBidOptimizer just
    before it starts making bid-recommendation API calls."""
    if HOTFIX_ACTIVE:
        _logger.warning(
            "HOTFIX active: suppressing deprecated bidRecommendations 429s "
            "while keeping per-keyword recommendations."
        )


# Apply the patch as soon as this module is imported.
_apply_hotfix()
