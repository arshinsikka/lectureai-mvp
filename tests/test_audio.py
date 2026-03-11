import pytest
from pathlib import Path
import tempfile
import struct
import wave

from app.services.audio import preprocess_audio, MAX_FILE_SIZE_BYTES

SAMPLE_AUDIO = Path("test_data/audio_1.mp3")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wav(path: Path, duration_seconds: float = 5.0, sample_rate: int = 44100) -> Path:
    """Write a minimal silent WAV file for testing."""
    num_samples = int(duration_seconds * sample_rate)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_samples)
    return path


# ---------------------------------------------------------------------------
# Core conversion test (uses real sample file)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not SAMPLE_AUDIO.exists(), reason="test_data/audio_1.mp3 not present")
def test_preprocess_real_file():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "audio_clean.wav"
        result = preprocess_audio(SAMPLE_AUDIO, out)

        assert result == out
        assert out.exists()
        assert out.stat().st_size > 0

        # Verify WAV properties
        with wave.open(str(out)) as wf:
            assert wf.getnchannels() == 1, "Expected mono"
            assert wf.getframerate() == 16_000, "Expected 16 kHz"


# ---------------------------------------------------------------------------
# Short audio warning (should still succeed)
# ---------------------------------------------------------------------------

def test_preprocess_short_audio_warns(tmp_path, caplog):
    """Files shorter than 60 s should trigger a warning but not fail."""
    import logging
    short_wav = _make_wav(tmp_path / "short.wav", duration_seconds=10.0)
    out = tmp_path / "out.wav"

    with caplog.at_level(logging.WARNING, logger="app.services.audio"):
        result = preprocess_audio(short_wav, out)

    assert result == out
    assert out.exists()
    assert any("short" in msg.lower() for msg in caplog.messages)


# ---------------------------------------------------------------------------
# Unsupported format
# ---------------------------------------------------------------------------

def test_preprocess_unsupported_format(tmp_path):
    bad_file = tmp_path / "audio.xyz"
    bad_file.write_bytes(b"not audio data")

    with pytest.raises(ValueError, match="Unsupported audio format"):
        preprocess_audio(bad_file, tmp_path / "out.wav")


# ---------------------------------------------------------------------------
# File too large (synthetic — we just mock the size via monkeypatch)
# ---------------------------------------------------------------------------

def test_preprocess_file_too_large(tmp_path, monkeypatch):
    audio_file = _make_wav(tmp_path / "big.wav", duration_seconds=5.0)
    out = tmp_path / "out.wav"

    # Pretend the file is huge without actually writing 500 MB
    import os
    original_stat = os.stat

    class FakeStat:
        st_size = MAX_FILE_SIZE_BYTES + 1

        def __getattr__(self, name):
            return getattr(original_stat(str(audio_file)), name)

    monkeypatch.setattr(Path, "stat", lambda self: FakeStat())

    with pytest.raises(ValueError, match="too large"):
        preprocess_audio(audio_file, out)


# ---------------------------------------------------------------------------
# Output directory is created automatically
# ---------------------------------------------------------------------------

def test_preprocess_creates_output_dir(tmp_path):
    src = _make_wav(tmp_path / "src.wav", duration_seconds=90.0)
    nested_out = tmp_path / "deeply" / "nested" / "audio_clean.wav"

    result = preprocess_audio(src, nested_out)
    assert result.exists()


# ---------------------------------------------------------------------------
# Verify mono + 16 kHz output from a synthetic stereo 44.1 kHz source
# ---------------------------------------------------------------------------

def test_preprocess_converts_sample_rate_and_channels(tmp_path):
    import wave
    stereo_wav = tmp_path / "stereo.wav"
    num_samples = int(90 * 44100)
    with wave.open(str(stereo_wav), "w") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(b"\x00\x00" * num_samples * 2)

    out = tmp_path / "clean.wav"
    preprocess_audio(stereo_wav, out)

    with wave.open(str(out)) as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 16_000
