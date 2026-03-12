# Sample Output — Neural Networks on Sequential Data

**Source:** NUS lecture, 101 minutes
**Pipeline:** LectureAI MVP (Whisper + Gemini 2.0 Flash)
**Processing time:** ~13 minutes
**API cost:** ~$0.61

This is a representative sample of the structured notes LectureAI generates. The `.docx` output includes the same content with proper Word formatting, a Mandarin section, and an action items table at the top.

---

## Action Items

| Item | Urgency | Mentioned At |
|---|---|---|
| PS40 problem set submission due this Friday | High | 00:08:43 |
| Makeup tutorial for students who missed the previous session — details on LumiNUS | Low | 00:09:12 |

---

## Topic 1: Why Sequential Data Requires a Different Approach

**Summary:**
- Standard feedforward neural networks treat each input independently and have no memory of previous inputs — this makes them unsuitable for data where order and history matter
- Sequential data (text, speech, time series, video) has dependencies that span varying distances: a pronoun depends on a noun that may have appeared 20 words earlier
- Fixed-size input windows (sliding window approach) capture only local context and fail when the relevant history is long or variable in length
- RNNs solve this by maintaining a hidden state that accumulates information across the sequence, giving the network an implicit memory

**Key Concepts:**
- **Sequential data:** Any data where the order of elements carries meaning — examples include sentences, audio waveforms, financial time series, and DNA sequences
- **Hidden state (h_t):** An internal vector that the RNN updates at each timestep, encoding information about the sequence seen so far
- **Temporal dependency:** A relationship between a current input and a past input that the model must capture to make accurate predictions

---

## Topic 2: Recurrent Neural Network (RNN) Architecture

**Summary:**
- The core RNN computation at each timestep: `h_t = tanh(W_h * h_{t-1} + W_x * x_t + b)` — the new hidden state is a function of the previous hidden state and the current input
- The same weight matrices (W_h, W_x) are shared across all timesteps — this is parameter efficiency and is what makes RNNs practical for variable-length sequences
- Output at each timestep: `y_t = W_y * h_t` — predictions can be made at every step (many-to-many) or only at the final step (many-to-one), depending on the task
- Backpropagation Through Time (BPTT) unrolls the RNN across timesteps and applies standard gradient descent — the same graph, just extended through time

**Key Concepts:**
- **Weight sharing:** Using the same parameters at every timestep, which keeps the model size constant regardless of sequence length
- **Many-to-many vs. many-to-one:** Many-to-many outputs a prediction at every timestep (e.g., POS tagging); many-to-one produces a single output after processing the full sequence (e.g., sentiment classification)
- **Backpropagation Through Time (BPTT):** The algorithm for computing gradients in an RNN by unrolling the recurrence and applying the chain rule across all timesteps

**Formulas:**
- Hidden state update: `h_t = tanh(W_h * h_{t-1} + W_x * x_t + b_h)`
- Output: `y_t = softmax(W_y * h_t + b_y)`

---

## Topic 3: The Vanishing Gradient Problem

**Summary:**
- When BPTT computes gradients for early timesteps, it multiplies the same weight matrix W_h repeatedly — if the largest eigenvalue of W_h is less than 1, gradients shrink exponentially toward zero
- In practice, this means RNNs struggle to learn dependencies that span more than ~10–20 timesteps — the gradient signal from distant past inputs essentially disappears
- The exploding gradient problem is the reverse: if the largest eigenvalue exceeds 1, gradients grow exponentially, causing numerical instability and divergence
- Gradient clipping is the standard fix for exploding gradients (cap gradient norm at a threshold); vanishing gradients require architectural solutions (LSTM, GRU)

**Key Concepts:**
- **Vanishing gradient:** Gradients becoming so small during BPTT that weights in early layers receive near-zero updates, preventing learning of long-range dependencies
- **Exploding gradient:** Gradients growing without bound during BPTT, typically addressed with gradient clipping
- **Gradient clipping:** Rescaling the gradient vector when its norm exceeds a threshold, preventing numerical overflow during training

---

## Topic 4: Long Short-Term Memory (LSTM) Networks

**Summary:**
- LSTM introduces a separate **cell state** (c_t) as a highway for gradient flow — the cell state is modified only through additive interactions, which prevents the multiplicative gradient degradation that affects vanilla RNNs
- Three gates control information flow: the **forget gate** decides what to erase from the cell state, the **input gate** decides what new information to write, and the **output gate** decides what to expose as the hidden state
- All three gates are sigmoid-activated vectors (values between 0 and 1) applied element-wise — a gate value near 0 blocks information, near 1 passes it
- LSTMs can learn to keep relevant information in the cell state for hundreds of timesteps, directly addressing the vanishing gradient problem

**Key Concepts:**
- **Cell state (c_t):** A separate memory vector maintained alongside the hidden state; modified additively, allowing gradients to flow back through time without degradation
- **Forget gate (f_t):** `sigmoid(W_f * [h_{t-1}, x_t] + b_f)` — controls how much of the previous cell state to retain
- **Input gate (i_t):** `sigmoid(W_i * [h_{t-1}, x_t] + b_i)` — controls how much of the new candidate cell state to write
- **Output gate (o_t):** `sigmoid(W_o * [h_{t-1}, x_t] + b_o)` — controls how much of the cell state to expose as the hidden state

**Formulas:**
- Forget gate: `f_t = sigmoid(W_f * [h_{t-1}, x_t] + b_f)`
- Input gate: `i_t = sigmoid(W_i * [h_{t-1}, x_t] + b_i)`
- Candidate cell: `c̃_t = tanh(W_c * [h_{t-1}, x_t] + b_c)`
- Cell state update: `c_t = f_t ⊙ c_{t-1} + i_t ⊙ c̃_t`
- Output gate: `o_t = sigmoid(W_o * [h_{t-1}, x_t] + b_o)`
- Hidden state: `h_t = o_t ⊙ tanh(c_t)`

---

## Topic 5: Gated Recurrent Units (GRU)

**Summary:**
- GRU simplifies LSTM by merging the forget and input gates into a single **update gate** and eliminating the separate cell state — h_t serves as both hidden state and memory
- The **reset gate** determines how much of the previous hidden state to use when computing the candidate hidden state — a reset gate near zero lets the unit ignore past context entirely
- GRU uses fewer parameters than LSTM, trains faster on smaller datasets, and achieves comparable performance on most sequence tasks
- Choice between LSTM and GRU is typically empirical — neither dominates universally, but GRU is often the better default when computational budget is limited

**Key Concepts:**
- **Update gate (z_t):** Controls the blend between the previous hidden state and the new candidate — acts as a combined forget/input mechanism
- **Reset gate (r_t):** Controls how much of the previous hidden state contributes to computing the new candidate hidden state
- **Parameter efficiency:** GRU has 2 gates vs. LSTM's 3, resulting in fewer weight matrices and faster training

**Formulas:**
- Update gate: `z_t = sigmoid(W_z * [h_{t-1}, x_t])`
- Reset gate: `r_t = sigmoid(W_r * [h_{t-1}, x_t])`
- Candidate: `h̃_t = tanh(W * [r_t ⊙ h_{t-1}, x_t])`
- Hidden state: `h_t = (1 - z_t) ⊙ h_{t-1} + z_t ⊙ h̃_t`

---

## Topic 6: Encoder-Decoder Architecture and Sequence-to-Sequence Models

**Summary:**
- Sequence-to-sequence (seq2seq) tasks map a variable-length input sequence to a variable-length output sequence — machine translation, summarisation, and question answering are canonical examples
- The encoder reads the full input sequence and compresses it into a fixed-size **context vector** (the final hidden state) — this vector is the only information the decoder receives about the input
- The decoder is an RNN that generates the output sequence token by token, conditioned on the context vector and its own previous outputs
- The fixed-size context vector is a bottleneck: long input sequences must be compressed into a single vector, causing information loss — attention mechanisms were developed specifically to address this limitation

**Key Concepts:**
- **Encoder:** An RNN that processes the input sequence and produces a context vector summarising the input
- **Decoder:** An RNN that generates the output sequence, initialised with the encoder's context vector
- **Context vector:** The encoder's final hidden state, representing the compressed meaning of the entire input sequence
- **Context vector bottleneck:** The information-theoretic constraint that all input information must pass through a fixed-size vector, limiting performance on long sequences

---

## Topic 7: Course Logistics and Assignments

**Summary:**
- PS40 problem set is due this Friday — submission through LumiNUS
- A makeup tutorial is scheduled for students who missed the previous session — check LumiNUS for the timeslot
- Next lecture will cover attention mechanisms and the Transformer architecture
- Office hours this week: Tuesday and Thursday 3–5pm, COM1 Level 2

**Action Items (repeated for visibility):**
- PS40 due this Friday — high urgency
- Check LumiNUS for makeup tutorial timeslot

---

*Generated by LectureAI — [github.com/arshinsikka/lectureai-mvp](https://github.com/arshinsikka/lectureai-mvp)*
