import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from openai import OpenAI
from pydub import AudioSegment

from app.config import get_settings

logger = logging.getLogger(__name__)

# Whisper API hard limit is 25 MB; we target 20 MB per chunk to stay safe.
WHISPER_MAX_BYTES = 25 * 1024 * 1024
CHUNK_TARGET_BYTES = 20 * 1024 * 1024  # 20 MB


def _bytes_per_second(audio: AudioSegment) -> int:
    """Bytes consumed per second for a pydub AudioSegment."""
    return audio.frame_rate * audio.sample_width * audio.channels


def _chunk_audio(audio: AudioSegment) -> list[tuple[float, AudioSegment]]:
    """
    Split *audio* into chunks each <= CHUNK_TARGET_BYTES.

    Returns a list of (start_seconds, chunk) tuples so callers can
    correct timestamps when merging.
    """
    bps = _bytes_per_second(audio)
    chunk_duration_ms = int((CHUNK_TARGET_BYTES / bps) * 1000)

    chunks: list[tuple[float, AudioSegment]] = []
    cursor_ms = 0
    total_ms = len(audio)

    while cursor_ms < total_ms:
        end_ms = min(cursor_ms + chunk_duration_ms, total_ms)
        chunks.append((cursor_ms / 1000.0, audio[cursor_ms:end_ms]))
        cursor_ms = end_ms

    return chunks


def _transcribe_chunk(
    client: OpenAI,
    chunk: AudioSegment,
    chunk_index: int,
    model: str,
) -> dict[str, Any]:
    """Export one chunk to a temp WAV and call the Whisper API."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        chunk.export(str(tmp_path), format="wav")

    try:
        logger.info("Transcribing chunk %d (%d s)…", chunk_index, len(chunk) // 1000)
        with open(tmp_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model=model,
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
        return response.model_dump()
    finally:
        tmp_path.unlink(missing_ok=True)


def _merge_chunks(
    chunk_results: list[tuple[float, dict[str, Any]]],
) -> dict[str, Any]:
    """
    Merge per-chunk Whisper responses into a single transcript dict.

    Each entry in chunk_results is (start_offset_seconds, whisper_response_dict).
    """
    merged_segments: list[dict[str, Any]] = []
    full_texts: list[str] = []

    for offset, result in chunk_results:
        raw_segments = result.get("segments") or []
        for seg in raw_segments:
            merged_segments.append(
                {
                    "start": round(seg["start"] + offset, 3),
                    "end": round(seg["end"] + offset, 3),
                    "text": seg["text"].strip(),
                }
            )
        chunk_text = (result.get("text") or "").strip()
        if chunk_text:
            full_texts.append(chunk_text)

    full_text = " ".join(full_texts)
    duration_seconds = merged_segments[-1]["end"] if merged_segments else 0.0
    word_count = len(full_text.split())

    return {
        "segments": merged_segments,
        "full_text": full_text,
        "duration_minutes": round(duration_seconds / 60, 2),
        "word_count": word_count,
    }


def transcribe_audio(session_id: str) -> Path:
    """
    Transcribe the cleaned audio for *session_id* using the Whisper API.

    Locates data/{session_id}/audio_clean.wav automatically.
    Files > 25 MB are split into ~20 MB chunks before sending to Whisper,
    and the per-chunk timestamps are corrected when merging.

    Saves results to data/{session_id}/transcript_raw.json and returns
    that path.

    Raises:
        FileNotFoundError: audio_clean.wav does not exist for the session.
        ValueError:         OPENAI_API_KEY not configured.
    """
    settings = get_settings()
    wav_path = settings.session_data_dir(session_id) / "audio_clean.wav"

    if not wav_path.exists():
        raise FileNotFoundError(
            f"audio_clean.wav not found for session '{session_id}'. "
            "Run preprocess_session_audio(session_id) first."
        )

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set in .env / environment.")

    client = OpenAI(api_key=settings.openai_api_key)
    model = settings.whisper_model

    audio = AudioSegment.from_file(str(wav_path))
    file_size = wav_path.stat().st_size
    logger.info(
        "[%s] Audio loaded: %.1f MB, %.2f min",
        session_id,
        file_size / 1024**2,
        len(audio) / 60_000,
    )

    if file_size <= WHISPER_MAX_BYTES:
        logger.info("[%s] File under 25 MB — single-pass transcription.", session_id)
        chunks_with_offsets: list[tuple[float, AudioSegment]] = [(0.0, audio)]
    else:
        chunks = _chunk_audio(audio)
        logger.info("[%s] File over 25 MB — splitting into %d chunks.", session_id, len(chunks))
        chunks_with_offsets = chunks

    chunk_results: list[tuple[float, dict[str, Any]]] = []
    for idx, (offset, chunk) in enumerate(chunks_with_offsets):
        result = _transcribe_chunk(client, chunk, idx, model)
        chunk_results.append((offset, result))

    transcript = _merge_chunks(chunk_results)

    logger.info(
        "[%s] Transcription done: %.2f min, %d words, %d segments.",
        session_id,
        transcript["duration_minutes"],
        transcript["word_count"],
        len(transcript["segments"]),
    )

    output_path = settings.session_data_dir(session_id) / "transcript_raw.json"
    output_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2))
    logger.info("[%s] Saved → %s", session_id, output_path)

    return output_path


# Backwards-compatible alias used by existing tests
transcribe = transcribe_audio
