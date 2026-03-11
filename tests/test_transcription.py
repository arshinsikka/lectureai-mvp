"""
Integration test for the transcription service.

Clips the first 2 minutes of test_data/audio_1.mp3, runs it through
Whisper (whisper-1), and prints the first 5 segments so you can
visually verify timestamps and text quality.

Requires:  OPENAI_API_KEY set in .env
Marks:     'integration' — skipped in CI unless --run-integration is passed.
"""
import json
import os
import tempfile
import wave
import pytest

from pathlib import Path
from pydub import AudioSegment

SAMPLE_MP3 = Path("test_data/audio_1.mp3")
CLIP_DURATION_MS = 2 * 60 * 1000  # 2 minutes


def pytest_addoption(parser):
    try:
        parser.addoption(
            "--run-integration",
            action="store_true",
            default=False,
            help="Run tests that hit live APIs (costs money).",
        )
    except ValueError:
        pass  # already added by another conftest


# ---------------------------------------------------------------------------
# Unit tests (no API calls)
# ---------------------------------------------------------------------------

def test_chunk_audio_splits_correctly():
    """Files > CHUNK_TARGET_BYTES should be split into multiple chunks."""
    from app.services.transcription import _chunk_audio, CHUNK_TARGET_BYTES

    # build a synthetic AudioSegment large enough to force splitting
    # 16 kHz mono 16-bit: 32 000 bytes/s → need > CHUNK_TARGET_BYTES total
    bps = 16_000 * 2 * 1  # 32 000 bytes/s
    target_seconds = int(CHUNK_TARGET_BYTES / bps) + 60  # definitely over one chunk

    audio = AudioSegment.silent(duration=target_seconds * 1000, frame_rate=16_000)
    chunks = _chunk_audio(audio)

    assert len(chunks) >= 2, "Expected at least 2 chunks for large audio"
    # offsets must be monotonically increasing
    offsets = [offset for offset, _ in chunks]
    assert offsets == sorted(offsets)
    assert offsets[0] == 0.0


def test_merge_chunks_corrects_timestamps():
    """Timestamps in chunk 2 must be shifted by chunk 1's duration."""
    from app.services.transcription import _merge_chunks

    chunk_results = [
        (0.0, {
            "text": "Hello world.",
            "segments": [
                {"start": 0.0, "end": 2.5, "text": "Hello world."},
            ],
        }),
        (300.0, {  # second chunk starts at t=300 s
            "text": "Next section.",
            "segments": [
                {"start": 0.0, "end": 3.1, "text": "Next section."},
            ],
        }),
    ]

    merged = _merge_chunks(chunk_results)

    assert merged["segments"][0]["start"] == 0.0
    assert merged["segments"][1]["start"] == 300.0
    assert merged["segments"][1]["end"] == pytest.approx(303.1, abs=0.01)
    assert "Hello world" in merged["full_text"]
    assert "Next section" in merged["full_text"]
    assert merged["word_count"] == 4


def test_merge_chunks_single_chunk():
    from app.services.transcription import _merge_chunks

    result = _merge_chunks([(0.0, {
        "text": "Only chunk.",
        "segments": [{"start": 1.0, "end": 2.0, "text": "Only chunk."}],
    })])
    assert len(result["segments"]) == 1
    assert result["full_text"] == "Only chunk."


# ---------------------------------------------------------------------------
# Integration test — clips first 2 min and hits the real Whisper API
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not SAMPLE_MP3.exists(),
    reason="test_data/audio_1.mp3 not present",
)
def test_transcribe_first_two_minutes(request):
    """
    Send the first 2 minutes of the sample lecture to Whisper and
    print the first 5 segments.  Skipped unless --run-integration.
    """
    if not request.config.getoption("--run-integration", default=False):
        pytest.skip("Pass --run-integration to run API tests.")

    from app.services.transcription import transcribe_audio
    from app.config import get_settings
    import app.config as cfg_mod

    settings = get_settings()
    if not settings.openai_api_key:
        pytest.skip("OPENAI_API_KEY not set.")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        session_id = "test-2min"

        # Clip to 2 minutes and save as audio_clean.wav in the session dir
        full_audio = AudioSegment.from_file(str(SAMPLE_MP3))
        clip = full_audio[:CLIP_DURATION_MS].set_channels(1).set_frame_rate(16_000)
        wav_path = tmp_path / session_id / "audio_clean.wav"
        wav_path.parent.mkdir(parents=True)
        clip.export(str(wav_path), format="wav")

        # Redirect DATA_DIR so the service writes into our temp dir
        os.environ["DATA_DIR"] = str(tmp_path)
        cfg_mod.get_settings.cache_clear()

        try:
            result_path = transcribe_audio(session_id)
        finally:
            os.environ.pop("DATA_DIR", None)
            cfg_mod.get_settings.cache_clear()

        assert result_path.exists(), "transcript_raw.json not written"
        data = json.loads(result_path.read_text())

        # Schema checks
        assert "segments" in data
        assert "full_text" in data
        assert "duration_minutes" in data
        assert "word_count" in data
        assert isinstance(data["segments"], list)
        assert len(data["segments"]) > 0
        assert data["word_count"] > 0

        # Print first 5 segments for manual inspection
        print("\n=== First 5 Whisper segments ===")
        for seg in data["segments"][:5]:
            print(f"  [{seg['start']:>7.2f}s → {seg['end']:>7.2f}s]  {seg['text']}")
        print(f"\nFull text preview (first 300 chars):\n  {data['full_text'][:300]}")
        print(f"\nduration_minutes : {data['duration_minutes']}")
        print(f"word_count       : {data['word_count']}")
        print(f"total segments   : {len(data['segments'])}")
