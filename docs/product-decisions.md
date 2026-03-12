# Product Decisions — The Why Behind Every Feature

This document explains the thinking behind every significant product choice in LectureAI. It's written to give collaborators, investors, and future team members a clear picture of how we reason about users, tradeoffs, and what we chose not to build.

---

## Why This Problem

NUS has over 40,000 students across 17 faculties. Nearly every lecture is recorded on Panopto or Zoom. The recordings are accessible. The content is there.

And yet 72% of students we surveyed rewatch those recordings — not because they want to review the material, but because they failed to capture it the first time. They're re-watching to fill gaps in their notes, not to deepen understanding.

That's a failure of tooling, not a failure of students.

Existing tools make it worse:

- **Zoom auto-captions** are trained on clear American English. They fail on Singapore/Chinese/Indian accented speech and produce zero-structure output.
- **Otter.ai** generates unstructured transcripts with timestamps — still a 12,000-word wall of text for a 90-minute lecture.
- **ChatGPT** can help if you manually paste the transcript — but that assumes you already have an accurate transcript, and it requires 30 minutes of manual prompt engineering per lecture.

None of these tools understand *context*. They don't know what was on the slides. They can't distinguish technical vocabulary from speech errors. They don't produce study materials — they produce raw text that still requires significant student effort to become useful.

We decided to build the tool that treats the lecture recording as an input and produces a structured study document as the output, with no manual steps in between.

---

## Why Bilingual (English + Mandarin)

This was our sharpest product decision and the one with the clearest user signal.

230+ of our survey respondents — from a sample of 500+ NUS students — explicitly indicated a preference for study materials in Mandarin. That's not a niche. That's a substantial portion of the student body that is either studying in a second language or simply comprehends technical content faster in Mandarin.

No existing tool provides automatic bilingual academic lecture notes. That gap is our most defensible differentiator.

A few specific decisions we made around the translation:

**We translate the structured summary, not the raw transcript.** A Mandarin translation of a 12,000-word transcript is not useful. A Mandarin translation of 500 words of structured topic notes is exactly what a student needs for revision.

**Technical terms stay in English.** LSTM, RNN, Transformer, backpropagation — these terms appear in English in Chinese academic textbooks and Chinese research papers. Translating them to Chinese-only would actually make the notes less useful for exam revision, where the English term is what appears on assessments.

**We use mainland academic register.** On first use of an established Chinese CS term, we follow the convention `循环神经网络 (RNN)` — Chinese translation followed by the English abbreviation in parentheses. This is what students familiar with Chinese university CS materials recognise.

---

## Why Topic-Wise Notes Instead of Full Transcripts

We made a deliberate decision early on: LectureAI does not produce a cleaned-up transcript. It produces *notes*.

A transcript is 12,000 words. A 90-minute lecture worth of notes should be 600–800 words — organised by topic, with concepts defined, and with the filler stripped. That's what a good student would produce from two hours of effort. That's what LectureAI produces in 15 minutes.

Topic segmentation mirrors how lecturers actually structure content. A lecturer who teaches LSTM first, then GRU, then encoder-decoder architectures is organising their lecture into units. Our summarisation prompt extracts those units as discrete sections, using the slide structure as a guide. Each topic becomes a self-contained study unit — which means students can jump to the section they need for a specific exam question, not scroll through a wall of text.

Action items are extracted *separately* from notes, not buried within them. A deadline mentioned at minute 8 of a 90-minute lecture is easy to miss. It appears at the top of the LectureAI output with an urgency label.

---

## Why Slides as Context (RAG) Matters

This is the decision we're most proud of, and the one that took the most iteration to get right.

Whisper mishears technical vocabulary systematically. "LSTM" becomes "LS TM" or "el es tee em". "Backpropagation" becomes "back propagation". "Softmax" becomes "soft max" or occasionally "software max". These aren't random errors — they're predictable failures on low-frequency vocabulary that Whisper's training data underrepresents.

A generic correction prompt ("fix errors in this transcript") cannot fix these, because the model has no way to know what the correct term is in context. It might guess correctly, or it might confidently produce a different wrong answer.

Slide context solves this. When the correction prompt includes the text from a slide that reads "Long Short-Term Memory (LSTM)" and "Gated Recurrent Unit (GRU)", the model has ground truth. It can confidently correct "el es tee em" → "LSTM" because the right answer is literally in the context window.

We measured the improvement informally: on a 50-segment sample from the Neural Networks test lecture, technical term accuracy was meaningfully higher in the corrected output compared to raw Whisper output, on segments where Whisper had introduced a recognisable error.

This is what makes our notes better than "paste your transcript into ChatGPT". ChatGPT doesn't have your slides. We do.

---

## What We Deliberately Left Out of the MVP

Every one of these decisions was made explicitly — not by accident.

**Real-time transcription:** Adding real-time mode (WebSocket streaming, Whisper Streaming API) would increase pipeline complexity by an order of magnitude and require infrastructure that can't be validated on a laptop. Post-lecture delivery within 15 minutes is sufficient to prove demand. We can add real-time as a premium feature once the core is validated.

**Student accounts and dashboards:** Email delivery and direct download is enough to validate whether students find the notes useful. Building authentication, user management, and a dashboard before proving demand is classic premature scaling. If students are emailing us asking for a dashboard, we'll build one.

**Zoom/Panopto integration:** OAuth registration, webhook handling, and API integration with recording platforms adds weeks of development and external dependencies (approval processes, rate limits, API stability). Manual upload proves the same value proposition with far less risk. Once we have evidence of consistent demand, integration becomes worth the investment.

**Quiz and flashcard generation:** This is a clear extension of the note-taking pipeline and something users have asked for. It's not in the MVP because adding it now would split focus: we'd be shipping a study tool before we've validated the notes quality. Notes first, then flashcards.

**Speaker diarisation:** The vast majority of NUS lectures are delivered by a single lecturer. Multi-speaker diarisation adds complexity (pyannote.audio, GPU inference) for a feature that doesn't apply to most use cases. Worth revisiting for panel discussions or seminar formats.

**LaTeX formula rendering:** Plain-text formulas like `h_t = tanh(W_h * h_{t-1} + W_x * x_t + b)` are readable in a `.docx` file. Full LaTeX rendering requires either a custom document renderer or a PDF-first approach, which complicates the email attachment workflow. The incremental value over plain text doesn't justify the complexity at this stage.

---

## Pricing Strategy Thinking

We haven't launched paid pricing yet, but we've thought carefully about the model.

**Per-lecture cost floor:** At current API rates, a 60-minute lecture costs approximately $0.36–$0.50 to process (Whisper at $0.006/min, Gemini on free tier). At scale with negotiated API pricing, this drops further.

**University licensing model:** The natural customer is not the individual student — it's the department or faculty IT team. A flat per-semester license per department aligns pricing with value and removes the friction of per-student billing. A faculty of 2,000 students attending 200 hours of lectures per semester would pay for the processing cost plus a margin, negotiated at the department level.

**Comparison that makes the sale:** A part-time TA assigned to produce lecture notes for a single course costs hundreds of dollars per week of labour. LectureAI covers the entire faculty at a fraction of that cost. The business case is straightforward.

---

## Competitive Positioning

| Tool | What it does | LectureAI advantage |
|---|---|---|
| Zoom auto-captions | Inaccurate captions, no notes | Structured notes, slide context, bilingual, accurate captions |
| Otter.ai | Unstructured transcript, basic speaker labels | Topic segmentation, key concepts, Mandarin, action items |
| Notion AI | AI writing assistant | Purpose-built for lectures, automated pipeline, no manual effort |
| ChatGPT | General assistant | Automated end-to-end, slide context, bilingual, no copy-paste |
| Rev.com | Human transcription | 10x cheaper, 5x faster, structured output |

Our sharpest differentiator is the intersection of three things no other tool offers together: **lecture-specific structure**, **slide-context accuracy**, and **bilingual output**. Any one of these alone is table stakes. All three together, in a single automated pipeline, is the product.
