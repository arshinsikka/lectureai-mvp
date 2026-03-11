"""
Mandarin translation step — translates summary.json and action_items.json
headings/text into Simplified Chinese, adding _zh fields in-place.

Saves:
  data/{session_id}/summary_zh.json    — full summary with heading_zh / summary_zh per topic
  data/{session_id}/action_items_zh.json — action items with description_zh added
"""
import copy
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


# ---------------------------------------------------------------------------
# Gemini helper
# ---------------------------------------------------------------------------

def _call_gemini(client: Any, prompt: str) -> str:
    from google.genai import types
    from app.services.gemini_helper import call_gemini

    config = types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=8192,
        response_mime_type="application/json",
    )
    return call_gemini(client, GEMINI_MODEL, prompt, config)


def _extract_json(raw: str) -> Any:
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"[\[{][\s\S]*[\]}]", cleaned)
        if m:
            return json.loads(m.group(0))
        raise ValueError(f"Could not parse JSON from translation response:\n{raw[:400]}")


# ---------------------------------------------------------------------------
# Summary translation
# ---------------------------------------------------------------------------

def _translate_summary(client: Any, summary: dict, prompt_template: str) -> dict:
    """
    Translate topic headings and summary bullet points.
    Returns a new summary dict with heading_zh and summary_zh added per topic.

    Sends a minimal payload (just the translatable text) to keep the prompt compact.
    """
    # Build a minimal payload — only the fields that need translation
    payload = {
        "lecture_title": summary.get("lecture_title", ""),
        "topics": [
            {
                "heading": t["heading"],
                "summary": t["summary"],
                # key_concepts definitions are translated too
                "key_concepts": [{"term": kc["term"], "definition": kc["definition"]}
                                  for kc in t.get("key_concepts", [])],
            }
            for t in summary.get("topics", [])
        ],
    }

    prompt = prompt_template.replace("{payload}", json.dumps(payload, ensure_ascii=False))
    raw = _call_gemini(client, prompt)
    translated = _extract_json(raw)

    # Merge zh fields back into a deep copy of the original
    result = copy.deepcopy(summary)
    result["lecture_title_zh"] = translated.get("lecture_title", "")
    translated_topics = translated.get("topics", [])

    for i, topic in enumerate(result["topics"]):
        if i < len(translated_topics):
            zh = translated_topics[i]
            topic["heading_zh"] = zh.get("heading", "")
            topic["summary_zh"] = zh.get("summary", [])
            # Merge zh definitions into key_concepts
            zh_concepts = zh.get("key_concepts", [])
            for j, kc in enumerate(topic.get("key_concepts", [])):
                if j < len(zh_concepts):
                    kc["definition_zh"] = zh_concepts[j].get("definition", "")
        else:
            topic["heading_zh"] = ""
            topic["summary_zh"] = []

    return result


# ---------------------------------------------------------------------------
# Action items translation
# ---------------------------------------------------------------------------

def _translate_action_items(client: Any, items: list, prompt_template: str) -> list:
    """Translate action item descriptions. Returns list with description_zh added."""
    if not items:
        return []

    payload = [{"description": it["description"]} for it in items]
    prompt = prompt_template.replace("{payload}", json.dumps(payload, ensure_ascii=False))
    raw = _call_gemini(client, prompt)
    translated = _extract_json(raw)

    result = copy.deepcopy(items)
    if isinstance(translated, list):
        for i, item in enumerate(result):
            if i < len(translated):
                t = translated[i]
                item["description_zh"] = (t.get("description") or "").strip()
            else:
                item["description_zh"] = ""
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def translate_outputs(session_id: str) -> tuple[Path, Path]:
    """
    Translate summary.json and action_items.json into Mandarin.

    Saves:
      data/{session_id}/summary_zh.json
      data/{session_id}/action_items_zh.json

    If translation fails for either file, logs the error and writes the
    original content with a "translation_error" flag rather than crashing.

    Returns (summary_zh_path, action_items_zh_path).
    """
    from app.config import get_settings
    from google import genai

    settings = get_settings()
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY not set.")

    session_dir = settings.session_data_dir(session_id)
    prompt_template = (Path(__file__).parent.parent / "prompts" / "translation.txt").read_text()
    client = genai.Client(api_key=settings.google_api_key)

    # ── Summary translation ──────────────────────────────────────────────────
    summary_zh_path = session_dir / "summary_zh.json"
    summary_path = session_dir / "summary.json"

    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        try:
            logger.info("[%s] Translating summary (%d topics)…", session_id, len(summary.get("topics", [])))
            summary_zh = _translate_summary(client, summary, prompt_template)
        except Exception as exc:  # noqa: BLE001
            logger.error("[%s] Summary translation failed: %s — saving with flag.", session_id, exc)
            summary_zh = copy.deepcopy(summary)
            summary_zh["translation_error"] = str(exc)
    else:
        logger.warning("[%s] summary.json not found — skipping summary translation.", session_id)
        summary_zh = {"translation_error": "summary.json missing"}

    summary_zh_path.write_text(json.dumps(summary_zh, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("[%s] Saved summary_zh.json", session_id)

    # ── Action items translation ─────────────────────────────────────────────
    ai_zh_path = session_dir / "action_items_zh.json"
    ai_path = session_dir / "action_items.json"

    if ai_path.exists():
        items = json.loads(ai_path.read_text(encoding="utf-8"))
        try:
            logger.info("[%s] Translating %d action item(s)…", session_id, len(items))
            items_zh = _translate_action_items(client, items, prompt_template)
        except Exception as exc:  # noqa: BLE001
            logger.error("[%s] Action items translation failed: %s — saving originals.", session_id, exc)
            items_zh = copy.deepcopy(items)
            for it in items_zh:
                it["translation_error"] = str(exc)
    else:
        logger.warning("[%s] action_items.json not found — skipping.", session_id)
        items_zh = []

    ai_zh_path.write_text(json.dumps(items_zh, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("[%s] Saved action_items_zh.json", session_id)

    return summary_zh_path, ai_zh_path
