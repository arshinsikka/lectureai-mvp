from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import upload, pipeline, results
from app.models import PingResponse

app = FastAPI(title="LectureAI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api")
app.include_router(pipeline.router, prefix="/api")
app.include_router(results.router, prefix="/api")


@app.get("/api/ping", response_model=PingResponse)
async def ping():
    return {"status": "ok"}
