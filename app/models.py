from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class PipelineStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class UploadResponse(BaseModel):
    session_id: str
    message: str
    audio_filename: str
    context_filenames: List[str]


class PipelineRequest(BaseModel):
    session_id: str
    language: Optional[str] = "en"
    translate_to: Optional[str] = "zh"
    send_email: Optional[bool] = False
    recipient_email: Optional[str] = None


class StatusResponse(BaseModel):
    session_id: str
    status: PipelineStatus
    step: Optional[str] = None
    progress: Optional[int] = 0
    error: Optional[str] = None
    steps_completed: Optional[List[str]] = None
    email_sent: Optional[bool] = None
    email_error: Optional[str] = None


class ResultsResponse(BaseModel):
    session_id: str
    transcript: Optional[str] = None
    corrected_transcript: Optional[str] = None
    summary: Optional[str] = None
    summary_zh: Optional[str] = None
    action_items: Optional[List[str]] = None
    docx_url: Optional[str] = None
    srt_url: Optional[str] = None
    vtt_url: Optional[str] = None


class PingResponse(BaseModel):
    status: str
