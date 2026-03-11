import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.config import get_settings
from app.models import PipelineRequest, PipelineStatus, StatusResponse

logger = logging.getLogger(__name__)
router = APIRouter()

_executor = ThreadPoolExecutor(max_workers=2)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _status_from_file(session_id: str) -> dict | None:
    """Read status.json from the session data dir. Returns None if missing."""
    p = get_settings().session_data_dir(session_id) / "status.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def _run_pipeline_sync(session_id: str) -> None:
    from app.pipeline.orchestrator import run_pipeline
    try:
        run_pipeline(session_id)
    except Exception as exc:
        logger.error("[%s] Pipeline background task failed: %s", session_id, exc)


async def _run_pipeline_async(session_id: str) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_executor, _run_pipeline_sync, session_id)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/process/{session_id}", response_model=StatusResponse)
async def start_pipeline(session_id: str, background_tasks: BackgroundTasks):
    """Trigger the full pipeline for a session as a background task."""
    wav_path = get_settings().session_data_dir(session_id) / "audio_clean.wav"
    mp3_candidates = list(get_settings().session_data_dir(session_id).glob("*.mp3")) + \
                     list(get_settings().session_data_dir(session_id).glob("*.m4a"))

    if not wav_path.exists() and not mp3_candidates:
        raise HTTPException(
            status_code=404,
            detail=f"No audio found for session '{session_id}'. Upload audio first.",
        )

    background_tasks.add_task(_run_pipeline_async, session_id)
    return StatusResponse(
        session_id=session_id,
        status=PipelineStatus.processing,
        step="queued",
        progress=0,
    )


@router.post("/process", response_model=StatusResponse)
async def start_pipeline_body(request: PipelineRequest, background_tasks: BackgroundTasks):
    """Trigger the full pipeline via JSON body (legacy endpoint)."""
    return await start_pipeline(request.session_id, background_tasks)


@router.post("/transcribe/{session_id}", response_model=StatusResponse)
async def start_transcription(session_id: str, background_tasks: BackgroundTasks):
    """Trigger Whisper transcription only."""
    from app.services.transcription import transcribe_audio

    wav_path = get_settings().session_data_dir(session_id) / "audio_clean.wav"
    if not wav_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"audio_clean.wav not found for session '{session_id}'.",
        )

    async def _run():
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor,
                                   lambda: transcribe_audio(session_id))

    background_tasks.add_task(_run)
    return StatusResponse(
        session_id=session_id,
        status=PipelineStatus.processing,
        step="transcription",
        progress=0,
    )


@router.get("/status/{session_id}", response_model=StatusResponse)
async def get_status(session_id: str):
    """Return the current pipeline status from status.json."""
    data = _status_from_file(session_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No status found for session '{session_id}'.")

    return StatusResponse(
        session_id=session_id,
        status=PipelineStatus(data.get("status", "pending")),
        step=data.get("current_step"),
        progress=data.get("progress", 0),
        error=data.get("error"),
        steps_completed=data.get("steps_completed", []),
        email_sent=data.get("email_sent"),
        email_error=data.get("email_error"),
    )
