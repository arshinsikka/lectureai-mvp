# Demo Guide — Running LectureAI End-to-End

This guide walks through a complete demo of LectureAI from file upload to finished notes. It's written for someone showing the product to a potential user, investor, or faculty member — or for a developer running it for the first time.

---

## Prerequisites

Before starting:

1. **Python 3.10+** and **ffmpeg** installed
   ```bash
   ffmpeg -version   # should print version info
   python3 --version # should be 3.10+
   ```

2. **Environment configured** — you need three API keys:
   ```bash
   cp .env.example .env
   # Fill in: OPENAI_API_KEY, GOOGLE_API_KEY, SMTP_EMAIL, SMTP_PASSWORD, RECIPIENT_EMAIL
   ```

3. **Server running:**
   ```bash
   source .venv/bin/activate
   uvicorn app.main:app --reload
   ```
   The API is live at `http://localhost:8000`. Confirm with:
   ```bash
   curl http://localhost:8000/api/ping
   # → {"status":"ok"}
   ```

4. **Frontend open** — open `frontend/index.html` in Chrome or Safari. No build step required.

---

## Step 1: Upload a Lecture

**Using the web interface:**

1. Open `frontend/index.html` in your browser
2. Click the audio upload area and select a lecture file (MP3, M4A, or WAV)
   - For demo purposes, use a 10–20 minute clip rather than a full 90-minute lecture to keep processing time short
3. Optionally upload lecture slides (PDF or PPTX) — this enables slide-context correction and is what makes LectureAI's accuracy distinctly better than raw Whisper
4. Click **Upload**
5. Note the `session_id` returned — it's a UUID like `a3f7c2e1-...` that identifies this session

**Using the API directly:**
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "audio=@test_data/audio_1.mp3" \
  -F "context_files=@test_data/Lecture 10 - Neural Networks on Sequential Data.pdf"
```

The response looks like:
```json
{
  "session_id": "a3f7c2e1-4b8d-4f2a-9c3e-1d5f8a2b7e9c",
  "audio_filename": "audio_1.mp3",
  "context_filenames": ["Lecture 10 - Neural Networks on Sequential Data.pdf"]
}
```

---

## Step 2: Start Processing

Click **Process** in the web interface, or:

```bash
curl -X POST http://localhost:8000/api/process/a3f7c2e1-4b8d-4f2a-9c3e-1d5f8a2b7e9c
```

The pipeline starts immediately in the background. It does not block.

---

## Step 3: Watch Progress

Poll the status endpoint (the frontend does this automatically every 3 seconds):

```bash
curl http://localhost:8000/api/status/a3f7c2e1-4b8d-4f2a-9c3e-1d5f8a2b7e9c
```

You'll see the step name and progress percentage update in real time:

| Progress | Step |
|---|---|
| 0–8% | Audio preprocessing |
| 8–22% | Whisper transcription |
| 22–28% | Parsing lecture slides |
| 28–45% | Correcting transcript with slide context |
| 45–58% | Generating topic-wise notes |
| 58–65% | Extracting action items |
| 65–75% | Translating to Mandarin |
| 75–85% | Generating .docx |
| 85–92% | Exporting captions (.srt / .vtt) |
| 92–100% | Sending email |

**Expected timeline:**
- 10-minute clip: ~4–5 minutes total
- 60-minute lecture: ~8–10 minutes total
- 101-minute lecture: ~12–15 minutes total

The bottleneck is Whisper transcription, which is network-bound (file upload to OpenAI, transcription, response download).

---

## Step 4: Examine the Outputs

Once status shows `"progress": 100`, retrieve the results:

```bash
curl http://localhost:8000/api/results/a3f7c2e1-4b8d-4f2a-9c3e-1d5f8a2b7e9c
```

The response includes download URLs and a preview of the notes content.

### Opening the .docx

Download and open `lecture_notes.docx`. Things to highlight:

- **Action items table at the top** — deadlines and announcements are front and centre, not buried in the notes. For the Neural Networks demo lecture, this shows the PS40 deadline.
- **Topic-wise structure** — not a wall of text. Each topic has a clear heading, 4–5 bullets, and a key concepts section with definitions. The structure mirrors the actual lecture flow.
- **English section first, Mandarin section second** — separated by a clear divider. The document is readable as English-only or as a bilingual study guide.
- **Technical terms in English within Mandarin text** — LSTM, RNN, GRU appear in English inside the Chinese paragraphs. This is deliberate; ask "why didn't you translate LSTM to Chinese?" — the answer is that students use the English term on exams.

### Opening the .srt Caption File

Download `captions.srt` and open in any text editor. The timestamps are accurate and the technical vocabulary is corrected. Compare the raw Whisper output in `data/{session_id}/transcript_raw.json` against the corrected version in `data/{session_id}/transcript_corrected.json` — this is where the slide context quality improvement is most visible.

To demo with video: if you have the original lecture video file, drag the `.srt` file into VLC alongside the video and it will display as subtitles. Or upload to a YouTube video as external captions.

### Checking the Email

If `RECIPIENT_EMAIL` was configured, open that inbox. The email should contain:
- A summary of what was processed (lecture title, number of topics, number of action items)
- Three attachments: `lecture_notes.docx`, `captions.srt`, `captions.vtt`

---

## Common Demo Questions and Answers

**"What happens if I upload without slides?"**
The pipeline still runs. Correction becomes grammar/punctuation cleanup only (no domain-specific fixes). Summarisation uses only the transcript. The output is still useful, just less accurate on technical vocabulary. This is the graceful degradation path — slides are optional but recommended.

**"How does it know where one topic ends and another begins?"**
The summarisation prompt instructs Gemini to identify natural topic boundaries in the transcript, using slide structure as a guide. When slides are available, section headers provide strong signals. Without slides, the model uses content transitions and the natural rhythm of how lecturers move between topics.

**"Can it handle Singapore/Chinese/Indian accented English?"**
Better than any video platform's built-in captions. Whisper was trained on a diverse corpus and handles accented English significantly better than caption systems trained primarily on broadcast English. The slide-context correction step further improves accuracy on technical vocabulary regardless of how it was pronounced.

**"What does it cost per lecture?"**
For a 60-minute lecture: approximately $0.36 for Whisper transcription, $0.00 for all Gemini steps (free tier). Under $0.40 total at current API pricing.

**"Is the data stored anywhere?"**
Session files are stored locally in `data/` and `outputs/` on the server running LectureAI. Nothing is sent to external storage. For a university deployment, this would run on university-managed infrastructure.

---

## Troubleshooting

**Rate limit errors (429) from Gemini:**
Gemini's free tier has per-minute request limits. The `gemini_helper.py` retry wrapper handles these automatically with a 60-second wait. If you're running multiple sessions simultaneously on a free tier key, queue them sequentially.

**Email not arriving:**
1. Check `SMTP_EMAIL` uses a Gmail App Password (not your account password) — standard passwords don't work with SMTP
2. Check spam folder
3. The pipeline still completes successfully if email fails — download the files via the API instead

**Whisper file size error:**
Files over 25MB are automatically split into overlapping chunks. If you're seeing an error, check that `ffmpeg` is installed and on your PATH — the chunking uses `pydub`, which calls `ffmpeg` internally.

**"Module not found" errors:**
Make sure you activated the virtual environment before running:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

**Pipeline stuck at a step:**
Check `data/{session_id}/status.json` directly — it contains the current step name and any error message. If a step failed, delete the `status.json` file and re-POST to `/api/process/{session_id}` — the pipeline will resume from the last completed checkpoint.
