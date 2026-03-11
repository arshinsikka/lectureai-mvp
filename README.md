<div align="center">
  <img src="assets/logo.png" alt="LectureAI" width="120" />

  # LectureAI

  **AI-powered lecture notes in minutes**

  [![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
  [![Gemini](https://img.shields.io/badge/Gemini-2.0%20Flash-4285F4?logo=google&logoColor=white)](https://ai.google.dev)
  [![Whisper](https://img.shields.io/badge/OpenAI-Whisper-412991?logo=openai&logoColor=white)](https://openai.com/research/whisper)
  [![License: MIT](https://img.shields.io/badge/License-MIT-D6249F.svg)](LICENSE)

  [Live Demo](https://lectureai.co) · [Report Bug](https://github.com/arshinsikka/lectureai-mvp/issues) · [Request Feature](https://github.com/arshinsikka/lectureai-mvp/issues)
</div>

---

## What is LectureAI?

LectureAI is an end-to-end AI pipeline that turns any lecture recording into structured, bilingual study notes. Upload an audio file (and optionally your lecture slides), and within minutes you receive topic-wise notes in both English and Mandarin, a list of action items and deadlines, and subtitle captions — all delivered to your inbox.

Built for NUS students and faculty, LectureAI reduces a 2-hour lecture to a 5-minute read while preserving every key concept, formula, and exam deadline the professor mentioned.

---

## Demo

> 🎬 **Demo video coming soon.**

<!--
Replace the placeholder below with your demo GIF or video thumbnail once recorded.
![LectureAI Demo](assets/demo.gif)
-->

<div align="center">
  <img src="assets/logo.png" alt="Demo placeholder" width="160" />
  <br/>
  <em>Drop your lecture → get bilingual notes in ~10 minutes</em>
</div>

---

## Features

| | Feature |
|---|---|
| ✅ | **Whisper-powered transcription** with robust accent and technical-term handling |
| ✅ | **AI transcript correction** using your lecture slides as grounding context |
| ✅ | **Topic-wise structured notes** with key concepts, definitions, and formulas |
| ✅ | **Bilingual output** — English notes + Mandarin (Simplified Chinese) translation |
| ✅ | **Automatic deadline extraction** — assignments, exams, and announcements |
| ✅ | **Caption export** (`.srt` / `.vtt`) compatible with Panopto, LumiNUS, and Canvas |
| ✅ | **Email delivery** — notes sent as a `.docx` attachment the moment they're ready |

---

## Architecture

The pipeline runs end-to-end as a background task after a single upload:

```mermaid
flowchart LR
    A([🎙️ Audio Upload]) --> B[Preprocess\naudio.py]
    B --> C[Transcribe\nWhisper API]
    C --> D[Parse Slides\nPyMuPDF / pptx]
    D --> E[Correct Transcript\nGemini 2.0 Flash]
    E --> F[Summarise\nGemini 2.0 Flash]
    F --> G[Extract Actions\nGemini 2.0 Flash]
    G --> H[Translate EN→ZH\nGemini 2.0 Flash]
    H --> I[Generate .docx\npython-docx]
    I --> J[Export Captions\n.srt / .vtt]
    J --> K([📧 Email Delivery])

    style A fill:#D6249F,color:#fff,stroke:none
    style K fill:#10B981,color:#fff,stroke:none
```

**Key design decisions:**
- Each session is isolated in `data/{session_id}/` — no cross-session state
- Long transcripts are split into overlapping 3 000-word chunks for correction
- All Gemini calls share a centralised retry wrapper: 60 s wait on 429, once-retry on other errors
- The pipeline writes `status.json` after every step so the frontend can poll live progress

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.10+, FastAPI, uvicorn |
| **Transcription** | OpenAI Whisper API (`whisper-1`) |
| **LLM / NLP** | Google Gemini 2.0 Flash (`google-genai`) |
| **Audio processing** | pydub — 16 kHz mono WAV normalisation |
| **Document generation** | python-docx |
| **Context parsing** | PyMuPDF (PDF), python-pptx (PPTX) |
| **Email** | Gmail SMTP via Python `smtplib` |
| **Frontend** | Vanilla JS, Tailwind CSS (CDN), Inter font |
| **Config** | pydantic-settings, python-dotenv |

---

## Quick Start

### Prerequisites

- Python 3.10+
- [OpenAI API key](https://platform.openai.com/api-keys)
- [Google AI API key](https://aistudio.google.com/app/apikey)
- `ffmpeg` installed — `brew install ffmpeg` on macOS, `apt install ffmpeg` on Linux

### 1. Clone

```bash
git clone https://github.com/arshinsikka/lectureai-mvp.git
cd lectureai-mvp
```

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Open .env and fill in your API keys
```

### 4. Run

```bash
uvicorn app.main:app --reload
```

| URL | Description |
|---|---|
| `http://localhost:8000` | API root |
| `http://localhost:8000/docs` | Swagger UI (interactive API docs) |
| `frontend/index.html` | Open in browser — no build step required |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/upload` | Upload audio + optional context files. Returns `session_id`. |
| `POST` | `/api/process/{session_id}` | Start the full pipeline as a background task. |
| `GET` | `/api/status/{session_id}` | Poll progress: step name, % complete, completion status. |
| `GET` | `/api/results/{session_id}` | Retrieve metadata and download URLs for completed outputs. |
| `GET` | `/api/download/{session_id}/{filename}` | Download a generated file (`.docx`, `.srt`, `.vtt`). |

Full interactive documentation: `http://localhost:8000/docs`

---

## Cost per Lecture

Approximate cost for a **60-minute lecture**:

| Step | Model | Estimated Cost |
|---|---|---|
| Transcription | OpenAI Whisper | ~$0.36 (60 min × $0.006/min) |
| Correction + Summarisation | Gemini 2.0 Flash | ~$0.05–0.15 |
| Translation | Gemini 2.0 Flash | ~$0.03–0.08 |
| **Total** | | **~$0.44–0.59 per lecture** |

> Gemini 2.0 Flash has a generous free tier (1 500 requests/day). Development and testing are essentially free.

---

## Roadmap

- [ ] **Zoom / MS Teams integration** — auto-ingest recordings from meeting platforms
- [ ] **Student dashboard** — session history, full-text search across past lectures
- [ ] **Multi-language support** — Spanish, Hindi, Malay (beyond EN + ZH)
- [ ] **LMS integration** — push notes directly to Canvas, Blackboard, or LumiNUS
- [ ] **AI quiz generation** — auto-generate MCQs and flashcards from topic sections

---

## Project Structure

```
lectureai-mvp/
├── app/
│   ├── main.py               # FastAPI app, CORS, router registration
│   ├── config.py             # pydantic-settings config + path helpers
│   ├── models.py             # Pydantic request/response models
│   ├── pipeline/
│   │   └── orchestrator.py   # Runs the full step sequence, writes status.json
│   ├── routes/
│   │   ├── upload.py         # POST /api/upload
│   │   ├── pipeline.py       # POST /api/process, GET /api/status
│   │   └── results.py        # GET /api/results, GET /api/download
│   ├── services/
│   │   ├── audio.py          # pydub preprocessing
│   │   ├── transcription.py  # Whisper API
│   │   ├── context_parser.py # PDF / PPTX slide extraction
│   │   ├── correction.py     # Gemini transcript correction (chunked)
│   │   ├── summarisation.py  # Gemini topic-wise notes
│   │   ├── action_items.py   # Gemini deadline extraction
│   │   ├── translation.py    # Gemini EN→ZH translation
│   │   ├── doc_generator.py  # python-docx output
│   │   ├── caption_export.py # .srt / .vtt generation
│   │   ├── email_sender.py   # Gmail SMTP delivery
│   │   └── gemini_helper.py  # Shared retry wrapper for all Gemini calls
│   └── prompts/              # Prompt templates (.txt)
├── frontend/
│   └── index.html            # Single-page app (no build step)
├── tests/                    # pytest unit + integration tests
├── assets/
│   └── logo.png
├── .env.example
├── requirements.txt
└── start.sh
```

---

## Team

Built at the **National University of Singapore (NUS)** to solve a real student pain point: 2-hour lectures, zero notes.

🌐 [lectureai.co](https://lectureai.co) · ✉️ hello@lectureai.co

---

## License

[MIT](LICENSE) © 2025 LectureAI
