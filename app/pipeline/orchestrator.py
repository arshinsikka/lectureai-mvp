"""
Full pipeline orchestrator with checkpoint recovery via status.json.

Step order and checkpoint file for each step:
  1.  preprocess    → audio_clean.wav
  2.  transcribe    → transcript_raw.json
  3.  parse_context → context_text.txt
  4.  correct       → transcript_corrected.json
  5.  summarise     → summary.json
  6.  action_items  → action_items.json
  7.  translate     → summary_zh.json
  8.  generate_doc  → outputs/{id}/lecture_notes.docx
  9.  export_captions → outputs/{id}/captions.srt
  10. send_email    → (no file; always re-runs unless flag set)
"""
import json
import logging
import traceback
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Status helpers ────────────────────────────────────────────────────────────

def _status_path(session_id: str) -> Path:
    from app.config import get_settings
    return get_settings().session_data_dir(session_id) / "status.json"


def _read_status(session_id: str) -> dict:
    p = _status_path(session_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"status": "pending", "progress": 0, "current_step": None,
            "steps_completed": [], "error": None}


def _write_status(session_id: str, status: str, progress: int,
                  current_step: str | None, steps_completed: list[str],
                  error: str | None = None,
                  email_sent: bool | None = None,
                  email_error: str | None = None) -> None:
    data = {
        "status": status,
        "progress": progress,
        "current_step": current_step,
        "steps_completed": steps_completed,
        "error": error,
    }
    if email_sent is not None:
        data["email_sent"] = email_sent
    if email_error is not None:
        data["email_error"] = email_error
    _status_path(session_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Step definitions ──────────────────────────────────────────────────────────

def _checkpoint(session_id: str, filename: str, in_outputs: bool = False) -> bool:
    """Return True if the checkpoint file already exists (step can be skipped)."""
    from app.config import get_settings
    settings = get_settings()
    if in_outputs:
        return (settings.session_outputs_dir(session_id) / filename).exists()
    return (settings.session_data_dir(session_id) / filename).exists()


STEPS: list[dict] = [
    {
        "name": "preprocess",
        "label": "Audio preprocessing",
        "checkpoint": "audio_clean.wav",
        "in_outputs": False,
        "progress": 8,
    },
    {
        "name": "transcribe",
        "label": "Whisper transcription",
        "checkpoint": "transcript_raw.json",
        "in_outputs": False,
        "progress": 22,
    },
    {
        "name": "parse_context",
        "label": "Context parsing",
        "checkpoint": "context_text.txt",
        "in_outputs": False,
        "progress": 28,
    },
    {
        "name": "correct",
        "label": "Transcript correction",
        "checkpoint": "transcript_corrected.json",
        "in_outputs": False,
        "progress": 45,
    },
    {
        "name": "summarise",
        "label": "Summarisation",
        "checkpoint": "summary.json",
        "in_outputs": False,
        "progress": 58,
    },
    {
        "name": "action_items",
        "label": "Action item extraction",
        "checkpoint": "action_items.json",
        "in_outputs": False,
        "progress": 65,
    },
    {
        "name": "translate",
        "label": "Mandarin translation",
        "checkpoint": "summary_zh.json",
        "in_outputs": False,
        "progress": 75,
    },
    {
        "name": "generate_doc",
        "label": "Document generation",
        "checkpoint": "lecture_notes.docx",
        "in_outputs": True,
        "progress": 85,
    },
    {
        "name": "export_captions",
        "label": "Caption export",
        "checkpoint": "captions.srt",
        "in_outputs": True,
        "progress": 92,
    },
    {
        "name": "send_email",
        "label": "Email delivery",
        "checkpoint": None,         # always attempt; soft-skip if unconfigured
        "in_outputs": False,
        "progress": 100,
    },
]


def _run_step(step_name: str, session_id: str) -> None:
    """Dispatch to the correct service function."""
    from app.services.audio          import preprocess_session_audio
    from app.services.transcription  import transcribe_audio
    from app.services.context_parser import parse_context_files
    from app.services.correction     import correct_transcript
    from app.services.summarisation  import summarise_lecture
    from app.services.action_items   import extract_action_items
    from app.services.translation    import translate_outputs
    from app.services.doc_generator  import generate_docx
    from app.services.caption_export import export_captions
    from app.services.email_sender   import send_results_email

    dispatch = {
        "preprocess":      lambda: preprocess_session_audio(session_id),
        "transcribe":      lambda: transcribe_audio(session_id),
        "parse_context":   lambda: parse_context_files(session_id),
        "correct":         lambda: correct_transcript(session_id),
        "summarise":       lambda: summarise_lecture(session_id),
        "action_items":    lambda: extract_action_items(session_id),
        "translate":       lambda: translate_outputs(session_id),
        "generate_doc":    lambda: generate_docx(session_id),
        "export_captions": lambda: export_captions(session_id),
        "send_email":      lambda: send_results_email(session_id),
    }
    dispatch[step_name]()


# ── Main entry point ──────────────────────────────────────────────────────────

def run_pipeline(session_id: str) -> None:
    """
    Run the full LectureAI pipeline for *session_id*.

    Resumes from the last completed step (checkpoint recovery).
    Writes data/{session_id}/status.json after every step.
    Stops immediately if any step raises an exception.
    """
    logger.info("[%s] Pipeline starting.", session_id)
    state = _read_status(session_id)
    completed: list[str] = state.get("steps_completed", [])

    _write_status(session_id, "processing", 0, None, completed)

    for step in STEPS:
        name     = step["name"]
        label    = step["label"]
        progress = step["progress"]
        checkpoint = step["checkpoint"]
        in_outputs = step["in_outputs"]

        # Skip if already completed (checkpoint exists)
        if checkpoint and _checkpoint(session_id, checkpoint, in_outputs):
            logger.info("[%s] ✓ Skipping '%s' (checkpoint exists).", session_id, name)
            if name not in completed:
                completed.append(name)
            _write_status(session_id, "processing", progress, name, completed)
            continue

        logger.info("[%s] → Running step: %s", session_id, label)
        _write_status(session_id, "processing", progress - 1, name, completed)

        # send_email is handled separately: failures must not abort the pipeline
        if name == "send_email":
            from app.services.email_sender import send_results_email
            try:
                sent, email_err = send_results_email(session_id)
            except Exception as exc:
                sent, email_err = False, str(exc)
            if name not in completed:
                completed.append(name)
            _write_status(session_id, "processing", progress, name, completed,
                          email_sent=sent, email_error=email_err)
            logger.info("[%s] ✓ Email step done (sent=%s, error=%s)",
                        session_id, sent, email_err)
            continue

        try:
            _run_step(name, session_id)
        except Exception as exc:
            err_msg = f"Step '{name}' failed: {exc}"
            logger.error("[%s] %s\n%s", session_id, err_msg, traceback.format_exc())
            _write_status(session_id, "failed", progress - 1, name, completed,
                          error=err_msg)
            raise RuntimeError(err_msg) from exc

        if name not in completed:
            completed.append(name)
        _write_status(session_id, "processing", progress, name, completed)
        logger.info("[%s] ✓ Completed '%s' (%d%%)", session_id, name, progress)

    _write_status(session_id, "completed", 100, None, completed)
    logger.info("[%s] Pipeline completed successfully.", session_id)
