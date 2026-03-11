import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import get_settings
from app.models import ResultsResponse

router = APIRouter()


@router.get("/results/{session_id}", response_model=ResultsResponse)
async def get_results(session_id: str):
    """Return metadata and download URLs for completed pipeline outputs."""
    settings = get_settings()
    session_dir = settings.session_data_dir(session_id)
    outputs_dir = settings.session_outputs_dir(session_id)

    # Must have at least a corrected transcript to have results
    if not (session_dir / "transcript_corrected.json").exists():
        raise HTTPException(status_code=404, detail="Results not ready for this session.")

    # Load transcript metadata
    td = json.loads((session_dir / "transcript_corrected.json").read_text(encoding="utf-8"))

    # Optional fields
    summary_text = None
    summary_zh_text = None
    action_items: list[str] | None = None

    if (session_dir / "summary.json").exists():
        s = json.loads((session_dir / "summary.json").read_text(encoding="utf-8"))
        summary_text = s.get("lecture_title", "")

    if (session_dir / "summary_zh.json").exists():
        s = json.loads((session_dir / "summary_zh.json").read_text(encoding="utf-8"))
        summary_zh_text = s.get("lecture_title_zh", "")

    if (session_dir / "action_items.json").exists():
        items = json.loads((session_dir / "action_items.json").read_text(encoding="utf-8"))
        action_items = [it["description"] for it in items]

    base = f"/api/download/{session_id}"
    docx_url = f"{base}/lecture_notes.docx" if (outputs_dir / "lecture_notes.docx").exists() else None
    srt_url  = f"{base}/captions.srt"       if (outputs_dir / "captions.srt").exists()       else None
    vtt_url  = f"{base}/captions.vtt"       if (outputs_dir / "captions.vtt").exists()       else None

    return ResultsResponse(
        session_id=session_id,
        transcript=td.get("full_text", "")[:500],        # preview
        corrected_transcript=td.get("full_text", "")[:500],
        summary=summary_text,
        summary_zh=summary_zh_text,
        action_items=action_items,
        docx_url=docx_url,
        srt_url=srt_url,
        vtt_url=vtt_url,
    )


@router.get("/download/{session_id}/{filename}")
async def download_file(session_id: str, filename: str):
    """Serve a generated output file for download."""
    settings = get_settings()
    file_path = settings.session_outputs_dir(session_id) / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found.")

    media_type_map = {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".srt":  "text/plain",
        ".vtt":  "text/vtt",
    }
    media_type = media_type_map.get(file_path.suffix, "application/octet-stream")
    return FileResponse(path=str(file_path), media_type=media_type, filename=filename)
