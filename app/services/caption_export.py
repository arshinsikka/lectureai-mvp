"""
Caption export — converts transcript segments to SRT and WebVTT formats.
"""
import json
import logging
import textwrap
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_LINE_CHARS = 80


# ── Timestamp formatters ──────────────────────────────────────────────────────

def _srt_ts(seconds: float) -> str:
    """Format seconds as HH:MM:SS,mmm (SRT)."""
    ms  = int(round(seconds * 1000))
    h   = ms // 3_600_000;  ms %= 3_600_000
    m   = ms // 60_000;     ms %= 60_000
    s   = ms // 1_000;      ms %= 1_000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _vtt_ts(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm (WebVTT)."""
    return _srt_ts(seconds).replace(",", ".")


# ── Text wrapping ─────────────────────────────────────────────────────────────

def _wrap_text(text: str, width: int = MAX_LINE_CHARS) -> str:
    """Wrap text so no line exceeds *width* characters."""
    text = text.strip()
    if len(text) <= width:
        return text
    return "\n".join(textwrap.wrap(text, width=width))


# ── Core export functions ─────────────────────────────────────────────────────

def export_srt(segments: list[dict], output_path: Path) -> Path:
    """
    Write *segments* as a standard SRT caption file.

    Each segment dict must have: start (float), end (float), text (str).
    Lines longer than MAX_LINE_CHARS are wrapped.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for idx, seg in enumerate(segments, start=1):
        text = _wrap_text(seg.get("text", "").strip())
        if not text:
            continue
        lines.append(str(idx))
        lines.append(f"{_srt_ts(seg['start'])} --> {_srt_ts(seg['end'])}")
        lines.append(text)
        lines.append("")   # blank line between blocks

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Saved SRT: %s (%d blocks)", output_path, idx)
    return output_path


def export_vtt(segments: list[dict], output_path: Path) -> Path:
    """
    Write *segments* as a WebVTT caption file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = ["WEBVTT", ""]
    idx = 1
    for seg in segments:
        text = _wrap_text(seg.get("text", "").strip())
        if not text:
            continue
        lines.append(str(idx))
        lines.append(f"{_vtt_ts(seg['start'])} --> {_vtt_ts(seg['end'])}")
        lines.append(text)
        lines.append("")
        idx += 1

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Saved VTT: %s (%d blocks)", output_path, idx - 1)
    return output_path


# ── Session-level entry point ─────────────────────────────────────────────────

def export_captions(session_id: str) -> tuple[Path, Path]:
    """
    Load transcript_corrected.json for *session_id* and write:
      outputs/{session_id}/captions.srt
      outputs/{session_id}/captions.vtt

    Returns (srt_path, vtt_path).
    """
    from app.config import get_settings

    settings = get_settings()
    session_dir = settings.session_data_dir(session_id)
    outputs_dir = settings.session_outputs_dir(session_id)

    transcript_path = session_dir / "transcript_corrected.json"
    if not transcript_path.exists():
        raise FileNotFoundError(
            f"transcript_corrected.json not found for session '{session_id}'."
        )

    data = json.loads(transcript_path.read_text(encoding="utf-8"))
    segments: list[dict] = data.get("segments", [])
    logger.info("[%s] Exporting captions for %d segments.", session_id, len(segments))

    srt_path = export_srt(segments, outputs_dir / "captions.srt")
    vtt_path = export_vtt(segments, outputs_dir / "captions.vtt")
    return srt_path, vtt_path
