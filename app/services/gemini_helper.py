"""
Shared Gemini call helper with centralised retry logic.

On 429 / resource_exhausted : wait 60 s, retry up to 3 times.
On any other exception       : retry once after 5 s.
Logs each retry attempt.
"""
import logging
import re
import time
from typing import Any

logger = logging.getLogger(__name__)

_RATE_LIMIT_WAIT = 60.0   # seconds to wait after a 429
_OTHER_ERROR_WAIT = 5.0   # seconds to wait before the single other-error retry
_MAX_429_RETRIES = 3


def _parse_retry_delay(exc: Exception) -> float | None:
    """Extract the API-suggested retry delay (seconds) from a 429 error string."""
    text = str(exc)
    m = re.search(r"'retryDelay':\s*'([\d.]+)s'", text)
    if m:
        return float(m.group(1)) + 2.0
    m = re.search(r"retry in ([\d.]+)s", text, re.IGNORECASE)
    if m:
        return float(m.group(1)) + 2.0
    return None


def _is_rate_limit(exc: Exception) -> bool:
    text = str(exc).lower()
    return "429" in text or "resource_exhausted" in text or "quota" in text


def call_gemini(client: Any, model: str, contents: str, config: Any) -> str:
    """
    Call client.models.generate_content and return response.text.

    Retry policy
    ------------
    - 429 / resource_exhausted : wait ``retryDelay`` from error body (or 60 s),
                                  retry up to _MAX_429_RETRIES times.
    - Any other exception       : retry ONCE after _OTHER_ERROR_WAIT seconds.

    Raises the last exception if all retries are exhausted.
    """
    rate_limit_attempts = 0
    other_error_retried = False

    while True:
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            return response.text

        except Exception as exc:
            if _is_rate_limit(exc):
                rate_limit_attempts += 1
                if rate_limit_attempts > _MAX_429_RETRIES:
                    logger.error(
                        "Gemini rate limit: exhausted %d retries — giving up.",
                        _MAX_429_RETRIES,
                    )
                    raise
                wait = _parse_retry_delay(exc) or _RATE_LIMIT_WAIT
                logger.warning(
                    "Gemini rate limit (429) — attempt %d/%d, waiting %.1f s…",
                    rate_limit_attempts, _MAX_429_RETRIES, wait,
                )
                time.sleep(wait)

            else:
                if other_error_retried:
                    logger.error("Gemini error on retry — giving up: %s", exc)
                    raise
                other_error_retried = True
                logger.warning(
                    "Gemini error — retrying once after %.1f s: %s",
                    _OTHER_ERROR_WAIT, exc,
                )
                time.sleep(_OTHER_ERROR_WAIT)
