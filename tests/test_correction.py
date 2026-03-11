"""
Tests for app/services/correction.py

Unit tests run with no API key.
Integration test (--run-integration) uses the transcript produced in
the transcription step and calls Gemini for real, then prints before/after.
"""
import json
import os
import tempfile
from pathlib import Path

import pytest

from app.services.correction import (
    _seconds_to_ts,
    _segments_to_prompt_lines,
    _parse_corrected_lines,
    _split_into_chunks,
    WORDS_PER_CHUNK,
    OVERLAP_WORDS,
)

# ---------------------------------------------------------------------------
# Unit: timestamp formatting
# ---------------------------------------------------------------------------

def test_seconds_to_ts():
    assert _seconds_to_ts(0) == "00:00:00"
    assert _seconds_to_ts(61) == "00:01:01"
    assert _seconds_to_ts(3661) == "01:01:01"


# ---------------------------------------------------------------------------
# Unit: segment → prompt lines
# ---------------------------------------------------------------------------

def test_segments_to_prompt_lines():
    segs = [
        {"start": 0.0, "end": 5.0, "text": "Hello world."},
        {"start": 5.0, "end": 10.0, "text": "Second segment."},
    ]
    lines = _segments_to_prompt_lines(segs)
    assert lines[0] == "[0] 00:00:00 Hello world."
    assert lines[1] == "[1] 00:00:05 Second segment."


# ---------------------------------------------------------------------------
# Unit: parse corrected lines back to segment dicts
# ---------------------------------------------------------------------------

def test_parse_corrected_lines_happy_path():
    original = [
        {"start": 0.0, "end": 3.0, "text": "gradiant decent"},
        {"start": 3.0, "end": 6.0, "text": "neural net works"},
    ]
    model_output = (
        "[0] 00:00:00 Gradient descent\n"
        "[1] 00:00:03 Neural networks\n"
    )
    result = _parse_corrected_lines(model_output, original)
    assert result[0]["text"] == "Gradient descent"
    assert result[1]["text"] == "Neural networks"
    assert result[0]["start"] == 0.0
    assert result[1]["start"] == 3.0


def test_parse_corrected_lines_fallback_on_missing():
    """If the model omits a segment number, fall back to original text."""
    original = [
        {"start": 0.0, "end": 3.0, "text": "original text"},
        {"start": 3.0, "end": 6.0, "text": "also original"},
    ]
    model_output = "[0] 00:00:00 Corrected text\n"  # segment 1 missing
    result = _parse_corrected_lines(model_output, original)
    assert result[0]["text"] == "Corrected text"
    assert result[1]["text"] == "also original"   # fallback


# ---------------------------------------------------------------------------
# Unit: chunk splitting
# ---------------------------------------------------------------------------

def _make_segments(n: int, words_each: int = 10) -> list[dict]:
    word = "word"
    return [
        {"start": float(i * 5), "end": float(i * 5 + 5),
         "text": " ".join([word] * words_each)}
        for i in range(n)
    ]


def test_split_small_transcript_is_one_chunk():
    segs = _make_segments(10, words_each=50)          # 500 words total
    chunks = _split_into_chunks(segs, words_per_chunk=3000, overlap_words=200)
    assert len(chunks) == 1
    assert chunks[0] == segs


def test_split_large_transcript_multi_chunk():
    # 400 segments × 10 words = 4000 words → should exceed WORDS_PER_CHUNK=3000
    segs = _make_segments(400, words_each=10)
    chunks = _split_into_chunks(segs, words_per_chunk=3000, overlap_words=200)
    assert len(chunks) >= 2


def test_split_overlap_means_chunks_share_segments():
    segs = _make_segments(400, words_each=10)
    chunks = _split_into_chunks(segs, words_per_chunk=3000, overlap_words=200)
    # Last segments of chunk[0] should appear at start of chunk[1]
    last_of_first = chunks[0][-1]
    first_of_second = chunks[1][0]
    # they should overlap
    assert last_of_first["start"] >= first_of_second["start"]


def test_split_covers_all_segments():
    """Every segment must appear in at least one chunk."""
    segs = _make_segments(500, words_each=10)
    chunks = _split_into_chunks(segs, words_per_chunk=3000, overlap_words=200)
    seen_starts = {seg["start"] for chunk in chunks for seg in chunk}
    all_starts = {seg["start"] for seg in segs}
    assert all_starts == seen_starts


# ---------------------------------------------------------------------------
# Integration: real Gemini call on the Day-3 transcript
# ---------------------------------------------------------------------------

def _find_latest_transcript() -> Path | None:
    data_dir = Path("data")
    if not data_dir.exists():
        return None
    for session_dir in sorted(data_dir.iterdir(), reverse=True):
        candidate = session_dir / "transcript_raw.json"
        if candidate.exists():
            return candidate
    return None


@pytest.mark.skipif(
    _find_latest_transcript() is None,
    reason="No transcript_raw.json found in data/ — run transcription first.",
)
def test_correct_transcript_integration(request):
    """
    Correct the most-recent raw transcript with Gemini and print
    3 before/after examples.  Requires --run-integration.
    """
    if not request.config.getoption("--run-integration", default=False):
        pytest.skip("Pass --run-integration to run API tests.")

    import asyncio
    import app.config as cfg_mod
    from app.services.correction import correct_transcript

    raw_path = _find_latest_transcript()
    session_id = raw_path.parent.name
    print(f"\nUsing session: {session_id}")

    result_path = asyncio.run(correct_transcript(session_id))
    assert result_path.exists(), "transcript_corrected.json was not written"

    # Load both for comparison
    raw_data = json.loads(raw_path.read_text())
    corr_data = json.loads(result_path.read_text())

    assert "segments" in corr_data
    assert "full_text" in corr_data
    assert len(corr_data["segments"]) == len(raw_data["segments"])
    assert corr_data["word_count"] > 0

    # Print 3 before/after examples
    raw_segs = raw_data["segments"]
    corr_segs = corr_data["segments"]

    print("\n=== Before / After correction (3 examples) ===")
    shown = 0
    for i, (r, c) in enumerate(zip(raw_segs, corr_segs)):
        if r["text"].strip() != c["text"].strip() and shown < 3:
            ts = _seconds_to_ts(r["start"])
            print(f"\n  [{ts}] BEFORE: {r['text']}")
            print(f"  [{ts}] AFTER:  {c['text']}")
            shown += 1

    if shown == 0:
        print("  (No differences found — transcript may already be clean)")

    print(f"\nTotal segments : {len(corr_segs)}")
    print(f"Word count     : {corr_data['word_count']}")
    print(f"Output path    : {result_path}")
