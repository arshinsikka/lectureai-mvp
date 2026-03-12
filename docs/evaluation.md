# Evaluation — How We Measure Quality

Shipping fast without measuring quality is how you build confidence in the wrong thing. This document describes how we evaluated LectureAI's outputs during development, what the results looked like, and what we would measure more rigorously at scale.

---

## Transcription Accuracy

**Baseline:** Raw Whisper output contains systematic errors on accented speech and technical vocabulary. For the Neural Networks test lecture, notable raw errors included: "LS TM" (should be LSTM), "reoccurrent" (recurrent), "back propagation" (backpropagation), "soft max" (softmax), and several course-specific proper nouns.

**After correction:** We manually compared 50 transcript segments from the Neural Networks test lecture (101 minutes, approximately 15,000 words). On segments where Whisper had introduced a recognisable technical vocabulary error, the corrected output matched the correct term in the overwhelming majority of cases. Slide context was the deciding factor — terms that appeared explicitly on slides were corrected reliably; terms not on any slide were corrected less consistently.

**Method:** Manual side-by-side comparison of `transcript_raw.json` and `transcript_corrected.json` against the actual lecture content (verified using the PDF slides).

**Known limitation:** Greeting segments, filler words, and conversational asides show no improvement — which is expected. There is nothing to correct in "Okay let's get started" regardless of slide context. This does not affect note quality.

---

## Summarisation Quality

**Lecture processed:** *Neural Networks on Sequential Data*, 101 minutes, NUS School of Computing

**Output:** 7 topics detected and organised

The 7 topics extracted from this lecture were:
1. Motivation for Sequential Models
2. Recurrent Neural Networks (RNN) Architecture
3. The Vanishing Gradient Problem
4. Long Short-Term Memory (LSTM) Networks
5. Gated Recurrent Units (GRU)
6. Encoder-Decoder Architecture and Sequence-to-Sequence Models
7. Course Logistics and Assignments

**Assessment:** Topics 1–6 map accurately to the actual slide sections (verified against the PDF). Topic 7 correctly identified administrative content as a separate section rather than mixing it into the technical notes. Each topic had 4–5 bullet points capturing the main ideas with appropriate specificity — not vague summaries like "LSTM was discussed" but concrete statements like "LSTM gates control what information is retained across timesteps, solving the vanishing gradient problem that limits standard RNNs."

Key concepts extracted per topic were spot-checked against slide content — terms like "hidden state," "cell state," "forget gate," and "encoder-decoder" were defined correctly and matched their definitions in the lecture.

---

## Action Item Extraction

**From the Neural Networks lecture, correctly identified:**

1. **PS40 problem set due next Friday** — urgency: high — mentioned at approximately 00:08:43
2. **Makeup tutorial announced for students who missed the previous session** — urgency: low

**Assessment:** Both items are genuine actionable items from the lecture. No false positives were identified in this test (no non-actionable content was mislabelled as a deadline or task). False positive rate needs a larger sample to characterise properly — a single lecture is insufficient to draw conclusions about precision.

**Known limitation:** Action items phrased indirectly ("You'll want to make sure you've submitted by end of week") are harder to extract reliably than explicit announcements ("PS40 is due this Friday"). Prompt tuning can improve recall here.

---

## Translation Quality

Translation was verified by a native Mandarin speaker on the team against the English summary.

**Technical term preservation:** LSTM, RNN, GRU, Transformer, backpropagation, softmax — all preserved in English in the Mandarin output. ✓

**Academic register:** The Mandarin translation reads at university level, consistent with how Chinese CS students encounter material in translated textbooks. ✓

**Structure preservation:** The JSON structure (topic headings, bullet arrays, key concept objects) is preserved correctly through the translation. The model does not accidentally translate JSON keys or field names. ✓

**Notable observation:** For terms with established Chinese translations (循环神经网络 for RNN, 长短期记忆网络 for LSTM), the model correctly applied the `Chinese term (English abbreviation)` convention on first use. Subsequent uses in the same section used the abbreviation only, which matches academic convention.

---

## Processing Performance

| Metric | Value |
|---|---|
| Lecture duration | 101 minutes |
| Total pipeline time | ~12–15 minutes |
| Whisper transcription time | ~4–6 minutes |
| Gemini correction time | ~3–4 minutes |
| Gemini summarisation time | ~2–3 minutes |
| Translation time | ~1–2 minutes |
| Document generation + email | < 1 minute |
| Per-lecture API cost | ~$0.50–$0.80 |
| Primary bottleneck | Whisper transcription (network-bound) |

Processing time scales approximately linearly with lecture duration. A 60-minute lecture completes in roughly 8–10 minutes. Network latency to OpenAI's Whisper API dominates total processing time.

---

## What We Would Measure at Scale

The MVP evaluation was manual and small-sample. At scale, we would instrument the following:

**Student satisfaction:** Post-delivery survey (one question: "How useful were these notes for your exam revision?" 1–5 scale). Target: 4.5/5 average. This is the single most important signal.

**Lecture coverage:** Percentage of key concepts mentioned in the lecture that appear in the generated notes. Method: manual spot-check sample of 10 lectures per semester, comparing notes against slide content.

**Technical term accuracy at scale:** Automated comparison of extracted technical terms against a ground-truth term list (built from slide text) across a corpus of 100+ lectures. This would give us a rigorous WER equivalent for domain vocabulary.

**Adoption rate:** Weekly active sessions per department. We'd want to see repeat usage — a professor uploading every lecture, not a one-time trial.

**A/B test:** Student performance on weekly quizzes in courses using LectureAI notes vs. control courses. This is the real outcome metric. Notes quality matters only insofar as it translates to better understanding. This is a semester-long study and would be the most credible validation of the product's value.
