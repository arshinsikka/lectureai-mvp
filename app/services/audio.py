import logging
from pathlib import Path

from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB
MIN_DURATION_SECONDS = 60

SUPPORTED_EXTENSIONS = {".mp3", ".m4a", ".wav", ".ogg", ".flac", ".webm", ".mp4"}


def preprocess_session_audio(session_id: str) -> Path:
    """
    Convenience wrapper: find the audio file in data/{session_id}/,
    run preprocessing, and return the path to audio_clean.wav.

    Raises FileNotFoundError if no supported audio file exists in the session dir.
    """
    from app.config import get_settings

    settings = get_settings()
    session_dir = settings.session_data_dir(session_id)

    # Find the first supported audio file in the session directory
    audio_file: Path | None = None
    for f in sorted(session_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
            audio_file = f
            break

    if audio_file is None:
        raise FileNotFoundError(
            f"No supported audio file found in {session_dir}. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    output_path = session_dir / "audio_clean.wav"
    logger.info("[%s] Preprocessing %s → %s", session_id, audio_file.name, output_path)
    return preprocess_audio(audio_file, output_path)


def preprocess_audio(input_path: Path, output_path: Path) -> Path:
    """
    Convert audio to 16 kHz mono WAV and normalise volume.

    Args:
        input_path:  Path to the raw uploaded audio file.
        output_path: Destination path for the cleaned WAV file
                     (e.g. data/{session_id}/audio_clean.wav).

    Returns:
        output_path on success.

    Raises:
        ValueError: File too large, unsupported format, or unreadable audio.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    # --- size check ---
    file_size = input_path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"Audio file is too large ({file_size / 1024**2:.1f} MB). "
            f"Maximum allowed size is 500 MB."
        )

    # --- format check ---
    ext = input_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported audio format '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # --- load audio ---
    try:
        # pydub uses ffmpeg under the hood
        audio = AudioSegment.from_file(str(input_path))
    except CouldntDecodeError as exc:
        raise ValueError(
            f"Could not decode audio file '{input_path.name}'. "
            "Ensure the file is a valid audio/video file and ffmpeg is installed."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Failed to load audio: {exc}") from exc

    # --- duration check ---
    duration_seconds = len(audio) / 1000.0
    duration_minutes = duration_seconds / 60.0
    logger.info("Audio duration: %.2f minutes (%.0f seconds)", duration_minutes, duration_seconds)

    if duration_seconds < MIN_DURATION_SECONDS:
        logger.warning(
            "Audio is very short (%.1f s < %d s). Continuing, but transcription quality "
            "may be low.",
            duration_seconds,
            MIN_DURATION_SECONDS,
        )

    # --- convert: mono, 16 kHz ---
    audio = audio.set_channels(1).set_frame_rate(16_000)

    # --- normalise volume to -20 dBFS target ---
    target_dbfs = -20.0
    change_db = target_dbfs - audio.dBFS
    audio = audio.apply_gain(change_db)
    logger.info(
        "Volume normalised: %.1f dBFS → %.1f dBFS (applied %+.1f dB)",
        audio.dBFS - change_db,
        audio.dBFS,
        change_db,
    )

    # --- export ---
    output_path.parent.mkdir(parents=True, exist_ok=True)
    audio.export(str(output_path), format="wav")
    logger.info("Cleaned audio saved to %s", output_path)

    return output_path
