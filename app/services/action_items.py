"""
Action item extraction — finds assignments, deadlines, exams, and
announcements from the corrected lecture transcript using Gemini.
"""
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.0-flash"
MAX_RETRIES = 4
BASE_BACKOFF = 2.0

_PROMPT = """\
You are an assistant that extracts action items, deadlines, announcements, \
and academic obligations from a university lecture transcript.

Carefully read the transcript and identify ALL of the following:
- Assignments or homework (with due dates if mentioned)
- Exam or quiz dates
- Project milestones or submission deadlines
- Administrative announcements (room changes, makeup tutorials, etc.)
- Anything a student must DO or REMEMBER

## Output format
Return ONLY a valid JSON array (no markdown, no explanation):

[
  {
    "type": "Assignment|Exam|Announcement|Deadline",
    "description": "concise description of the item",
    "due_date": "date/time string or null if not mentioned",
    "urgency": "high|medium|low"
  }
]

- Use "high" urgency for items due within 1 week or exam-related.
- Use "medium" for upcoming items without a close deadline.
- Use "low" for general announcements with no deadline.
- If there are NO action items at all, return an empty JSON array: []

## Lecture transcript
{transcript}
"""

VALID_TYPES = {"Assignment", "Exam", "Announcement", "Deadline"}
VALID_URGENCY = {"high", "medium", "low"}


def _call_gemini(client: Any, prompt: str) -> str:
    from google.genai import types
    from app.services.gemini_helper import call_gemini

    config = types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=4096,
        response_mime_type="application/json",
    )
    return call_gemini(client, GEMINI_MODEL, prompt, config)


def _normalise(items: list) -> list[dict]:
    """Validate and fill in defaults for each action item."""
    cleaned = []
    for item in items:
        if not isinstance(item, dict):
            continue
        cleaned.append({
            "type": item.get("type") if item.get("type") in VALID_TYPES else "Announcement",
            "description": str(item.get("description") or "").strip(),
            "due_date": item.get("due_date") or None,
            "urgency": item.get("urgency") if item.get("urgency") in VALID_URGENCY else "low",
        })
    return [i for i in cleaned if i["description"]]


def _extract_json_array(raw: str) -> list:
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    try:
        result = json.loads(cleaned)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        m = re.search(r"\[[\s\S]*\]", cleaned)
        if m:
            return json.loads(m.group(0))
        return []


def extract_action_items(session_id: str) -> Path:
    """
    Load transcript_corrected.txt, extract action items with Gemini,
    and save to data/{session_id}/action_items.json.

    Returns the path to action_items.json. Empty array is valid output.
    """
    from app.config import get_settings
    from google import genai

    settings = get_settings()
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY not set.")

    session_dir = settings.session_data_dir(session_id)
    txt_path = session_dir / "transcript_corrected.txt"
    if not txt_path.exists():
        raise FileNotFoundError(f"transcript_corrected.txt not found for session '{session_id}'.")

    transcript = txt_path.read_text(encoding="utf-8").strip()
    client = genai.Client(api_key=settings.google_api_key)

    logger.info("[%s] Extracting action items with %s…", session_id, GEMINI_MODEL)
    raw = _call_gemini(client, _PROMPT.replace("{transcript}", transcript))
    items = _normalise(_extract_json_array(raw))

    output_path = session_dir / "action_items.json"
    output_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("[%s] Saved action_items.json — %d item(s) found.", session_id, len(items))

    return output_path
