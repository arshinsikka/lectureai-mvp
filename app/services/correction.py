"""
LLM Step 1 — Transcript correction using Gemini (synchronous).

Loads the raw Whisper transcript, splits it into overlapping word-chunks,
corrects each with the lecture context as RAG, then merges back and saves.
"""
import json
import logging
import re
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.0-flash"
WORDS_PER_CHUNK = 3000
OVERLAP_WORDS = 200
MAX_RETRIES = 5
BASE_BACKOFF = 2.0          # seconds; doubles each retry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seconds_to_ts(seconds: float) -> str:
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _segments_to_prompt_lines(segments: list[dict]) -> list[str]:
    """Render segments as the numbered format the prompt expects."""
    return [f"[{i}] {_seconds_to_ts(seg['start'])} {seg['text']}"
            for i, seg in enumerate(segments)]


def _parse_corrected_lines(raw: str, original_segments: list[dict]) -> list[dict]:
    """
    Parse the model's '[N] HH:MM:SS text' output back into segment dicts.
    Falls back to the original text for any segment the model garbled.
    """
    corrected: dict[int, str] = {}
    pattern = re.compile(r"^\[(\d+)\]\s+\d{2}:\d{2}:\d{2}\s+(.*)", re.MULTILINE)
    for match in pattern.finditer(raw):
        corrected[int(match.group(1))] = match.group(2).strip()

    return [
        {"start": seg["start"], "end": seg["end"],
         "text": corrected.get(i, seg["text"])}
        for i, seg in enumerate(original_segments)
    ]


def _split_into_chunks(
    segments: list[dict],
    words_per_chunk: int = WORDS_PER_CHUNK,
    overlap_words: int = OVERLAP_WORDS,
) -> list[list[dict]]:
    """
    Group segments into chunks capped at ~words_per_chunk words.
    Consecutive chunks overlap by ~overlap_words words so we don't
    cut sentences at boundaries.
    """
    chunks: list[list[dict]] = []
    start_idx = 0

    while start_idx < len(segments):
        word_count = 0
        end_idx = start_idx
        while end_idx < len(segments):
            word_count += len(segments[end_idx]["text"].split())
            end_idx += 1
            if word_count >= words_per_chunk:
                break

        chunk = segments[start_idx:end_idx]
        chunks.append(chunk)

        if end_idx >= len(segments):
            break

        overlap_count = 0
        overlap_wc = 0
        for seg in reversed(chunk):
            overlap_wc += len(seg["text"].split())
            overlap_count += 1
            if overlap_wc >= overlap_words:
                break

        start_idx = end_idx - overlap_count

    return chunks


def _parse_retry_delay(exc: Exception) -> float | None:
    """Extract the API-suggested retry delay from a 429 error string."""
    text = str(exc)
    match = re.search(r"'retryDelay':\s*'([\d.]+)s'", text)
    if match:
        return float(match.group(1)) + 2.0
    match = re.search(r"retry in ([\d.]+)s", text, re.IGNORECASE)
    if match:
        return float(match.group(1)) + 2.0
    return None


def _call_gemini(client: Any, prompt: str, chunk_idx: int) -> str:
    """Call Gemini synchronously using the shared retry wrapper."""
    from google.genai import types
    from app.services.gemini_helper import call_gemini

    config = types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=8192,
    )
    logger.debug("[chunk %d] Calling Gemini…", chunk_idx)
    return call_gemini(client, GEMINI_MODEL, prompt, config)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def correct_transcript(session_id: str) -> Path:
    """
    Load transcript_raw.json, correct it with Gemini + context (synchronous),
    and save transcript_corrected.json + transcript_corrected.txt.

    Returns the path to transcript_corrected.json.
    """
    from app.config import get_settings
    from google import genai

    settings = get_settings()
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY is not set in .env / environment.")

    session_dir = settings.session_data_dir(session_id)
    raw_json_path = session_dir / "transcript_raw.json"
    if not raw_json_path.exists():
        raise FileNotFoundError(f"transcript_raw.json not found for session '{session_id}'.")

    raw_data: dict = json.loads(raw_json_path.read_text(encoding="utf-8"))
    segments: list[dict] = raw_data["segments"]

    context_path = session_dir / "context_text.txt"
    context = context_path.read_text(encoding="utf-8").strip() if context_path.exists() else ""
    if not context:
        logger.info("[%s] No context file — correcting grammar/punctuation only.", session_id)

    prompt_template = (Path(__file__).parent.parent / "prompts" / "correction.txt").read_text()
    client = genai.Client(api_key=settings.google_api_key)

    chunks = _split_into_chunks(segments)
    logger.info(
        "[%s] Correcting %d segments in %d chunk(s) with %s.",
        session_id, len(segments), len(chunks), GEMINI_MODEL,
    )

    # Build global start index for each chunk (accounting for overlap)
    chunk_start_indices: list[int] = []
    idx = 0
    for chunk_num, chunk in enumerate(chunks):
        chunk_start_indices.append(idx)
        if chunk_num < len(chunks) - 1:
            overlap_wc = overlap_count = 0
            for seg in reversed(chunk):
                overlap_wc += len(seg["text"].split())
                overlap_count += 1
                if overlap_wc >= OVERLAP_WORDS:
                    break
            idx += len(chunk) - overlap_count
        else:
            idx += len(chunk)

    corrected_map: dict[int, str] = {}
    for chunk_num, chunk in enumerate(chunks):
        global_offset = chunk_start_indices[chunk_num]
        chunk_text = "\n".join(_segments_to_prompt_lines(chunk))
        prompt = prompt_template.format(
            context=context or "(No context provided — correct grammar and punctuation only.)",
            transcript_chunk=chunk_text,
        )
        logger.info(
            "[%s] Chunk %d/%d: %d segments, ~%d words…",
            session_id, chunk_num + 1, len(chunks),
            len(chunk), sum(len(s["text"].split()) for s in chunk),
        )

        raw_response = _call_gemini(client, prompt, chunk_num)
        for local_idx, seg in enumerate(_parse_corrected_lines(raw_response, chunk)):
            corrected_map[global_offset + local_idx] = seg["text"]

    corrected_segments = [
        {"start": seg["start"], "end": seg["end"],
         "text": corrected_map.get(i, seg["text"])}
        for i, seg in enumerate(segments)
    ]
    full_corrected_text = " ".join(s["text"] for s in corrected_segments)

    corrected_data = {
        "segments": corrected_segments,
        "full_text": full_corrected_text,
        "duration_minutes": raw_data.get("duration_minutes", 0),
        "word_count": len(full_corrected_text.split()),
    }

    json_out = session_dir / "transcript_corrected.json"
    txt_out = session_dir / "transcript_corrected.txt"
    json_out.write_text(json.dumps(corrected_data, ensure_ascii=False, indent=2), encoding="utf-8")
    txt_out.write_text(full_corrected_text, encoding="utf-8")

    logger.info(
        "[%s] Correction complete — %d segments → %s",
        session_id, len(corrected_segments), json_out,
    )
    return json_out
