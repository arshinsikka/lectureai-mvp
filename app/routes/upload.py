import logging
import uuid
import aiofiles
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, UploadFile, HTTPException

from app.config import get_settings
from app.models import UploadResponse
from app.services.audio import preprocess_audio, MAX_FILE_SIZE_BYTES

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".mp4", ".m4a", ".wav", ".ogg", ".webm", ".flac"}
ALLOWED_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp4", "audio/wav", "audio/x-wav",
    "audio/ogg", "audio/webm", "audio/flac", "audio/m4a",
    "audio/x-m4a", "video/mp4", "video/webm",
}


def _is_valid_audio(upload: UploadFile) -> bool:
    if upload.content_type in ALLOWED_AUDIO_TYPES:
        return True
    ext = Path(upload.filename or "").suffix.lower()
    return ext in ALLOWED_AUDIO_EXTENSIONS


@router.post("/upload", response_model=UploadResponse)
async def upload_files(
    audio: UploadFile = File(...),
    context_files: Optional[List[UploadFile]] = File(default=None),
):
    settings = get_settings()

    if not _is_valid_audio(audio):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio type '{audio.content_type}'. "
                   f"Accepted extensions: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}",
        )

    session_id = str(uuid.uuid4())
    session_dir = settings.session_data_dir(session_id)

    # --- save raw audio ---
    audio_filename = audio.filename or f"audio{Path(audio.filename or '.mp3').suffix}"
    raw_audio_path = session_dir / audio_filename

    raw_bytes = await audio.read()

    # size guard before writing
    if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file exceeds 500 MB limit ({len(raw_bytes) / 1024**2:.1f} MB).",
        )

    async with aiofiles.open(raw_audio_path, "wb") as f:
        await f.write(raw_bytes)

    logger.info("[%s] Raw audio saved: %s", session_id, raw_audio_path)

    # --- preprocess audio ---
    clean_wav_path = session_dir / "audio_clean.wav"
    try:
        preprocess_audio(raw_audio_path, clean_wav_path)
        logger.info("[%s] Audio preprocessing complete: %s", session_id, clean_wav_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # --- save context files into context/ subdirectory ---
    saved_context: List[str] = []
    if context_files:
        context_dir = session_dir / "context"
        context_dir.mkdir(exist_ok=True)
        for ctx_file in context_files:
            if ctx_file.filename:
                ctx_path = context_dir / ctx_file.filename
                async with aiofiles.open(ctx_path, "wb") as f:
                    await f.write(await ctx_file.read())
                saved_context.append(ctx_file.filename)
                logger.info("[%s] Context file saved: %s", session_id, ctx_file.filename)

    return UploadResponse(
        session_id=session_id,
        message="Upload and audio preprocessing complete",
        audio_filename=audio_filename,
        context_filenames=saved_context,
    )
