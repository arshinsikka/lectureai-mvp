"""
LLM Step 2 — Topic-wise lecture summarisation using Gemini (synchronous).
"""
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.0-flash"
# Word count above which the transcript is chunked before summarising.
# Keeps each prompt comfortably within token limits.
CHUNK_WORD_LIMIT = 12_000
MAX_RETRIES = 4
BASE_BACKOFF = 2.0

# Minimum quality thresholds
MIN_SUMMARY_POINTS = 2


# ---------------------------------------------------------------------------
# Gemini call with retry
# ---------------------------------------------------------------------------

def _call_gemini(client: Any, prompt: str, use_json_mode: bool = True) -> str:
    from google.genai import types
    from app.services.gemini_helper import call_gemini

    config_kwargs: dict = dict(temperature=0.2, max_output_tokens=8192)
    if use_json_mode:
        config_kwargs["response_mime_type"] = "application/json"
    config = types.GenerateContentConfig(**config_kwargs)
    return call_gemini(client, GEMINI_MODEL, prompt, config)


def _parse_retry_delay(exc: Exception) -> float | None:
    text = str(exc)
    m = re.search(r"'retryDelay':\s*'([\d.]+)s'", text)
    if m:
        return float(m.group(1)) + 2.0
    m = re.search(r"retry in ([\d.]+)s", text, re.IGNORECASE)
    if m:
        return float(m.group(1)) + 2.0
    return None


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict:
    """
    Parse JSON from the model response, stripping markdown fences if present.
    Raises ValueError if no valid JSON object is found.
    """
    # Strip ```json ... ``` fences
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Last resort: find the first {...} block
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if m:
            return json.loads(m.group(0))
        raise ValueError(f"Could not extract JSON from model response:\n{raw[:500]}")


# ---------------------------------------------------------------------------
# Chunking for very long transcripts
# ---------------------------------------------------------------------------

def _chunk_text(text: str, max_words: int) -> list[str]:
    words = text.split()
    chunks, start = [], 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunks.append(" ".join(words[start:end]))
        start = end
    return chunks


def _merge_summaries(partial_results: list[dict]) -> dict:
    """Merge topic lists from multiple chunk summaries into one."""
    if len(partial_results) == 1:
        return partial_results[0]

    merged_topics: list[dict] = []
    title = partial_results[0].get("lecture_title", "")
    for result in partial_results:
        if not title and result.get("lecture_title"):
            title = result["lecture_title"]
        merged_topics.extend(result.get("topics", []))

    return {"lecture_title": title, "topics": merged_topics}


# ---------------------------------------------------------------------------
# Validation / normalisation
# ---------------------------------------------------------------------------

def _normalise_topic(topic: dict, idx: int) -> dict:
    """Ensure every topic has the required fields."""
    return {
        "heading": topic.get("heading") or f"Section {idx + 1}",
        "summary": topic.get("summary") or [],
        "key_concepts": topic.get("key_concepts") or [],
        "formulas": topic.get("formulas") or [],
    }


def _validate(data: dict) -> dict:
    data.setdefault("lecture_title", "Untitled Lecture")
    data["topics"] = [_normalise_topic(t, i) for i, t in enumerate(data.get("topics", []))]

    for topic in data["topics"]:
        if len(topic["summary"]) < MIN_SUMMARY_POINTS:
            logger.warning("Topic '%s' has only %d summary point(s).", topic["heading"], len(topic["summary"]))

    return data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def summarise_lecture(session_id: str) -> Path:
    """
    Load transcript_corrected.txt + context_text.txt, call Gemini to produce
    topic-wise structured notes, and save to data/{session_id}/summary.json.

    Returns the path to summary.json.
    """
    from app.config import get_settings
    from google import genai

    settings = get_settings()
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY not set.")

    session_dir = settings.session_data_dir(session_id)
    prompt_template = (Path(__file__).parent.parent / "prompts" / "summarisation.txt").read_text()

    # Load inputs
    txt_path = session_dir / "transcript_corrected.txt"
    if not txt_path.exists():
        raise FileNotFoundError(f"transcript_corrected.txt not found for session '{session_id}'.")

    transcript = txt_path.read_text(encoding="utf-8").strip()
    ctx_path = session_dir / "context_text.txt"
    context = ctx_path.read_text(encoding="utf-8").strip() if ctx_path.exists() else "(No slide context available.)"

    client = genai.Client(api_key=settings.google_api_key)
    word_count = len(transcript.split())
    logger.info("[%s] Summarising: %d words, model=%s", session_id, word_count, GEMINI_MODEL)

    # Chunk only if the transcript is very long
    if word_count <= CHUNK_WORD_LIMIT:
        chunks = [transcript]
    else:
        chunks = _chunk_text(transcript, CHUNK_WORD_LIMIT)
        logger.info("[%s] Transcript chunked into %d parts for summarisation.", session_id, len(chunks))

    partial_results: list[dict] = []
    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            logger.info("[%s] Summarising chunk %d/%d…", session_id, i + 1, len(chunks))
        prompt = prompt_template.replace("{context}", context).replace("{transcript}", chunk)
        raw = _call_gemini(client, prompt, use_json_mode=True)
        data = _extract_json(raw)
        partial_results.append(data)

    merged = _merge_summaries(partial_results)
    summary = _validate(merged)

    output_path = session_dir / "summary.json"
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("[%s] Saved summary.json — %d topics detected.", session_id, len(summary["topics"]))

    return output_path
