# exams

Course-level exams built from a question bank.

## Models
- **`QuestionBank`**: per-course questions, either `mcq` or `tf` (true/false), with difficulty and marks.
- **`Exam`**: questions from its course's bank, plus optional custom questions.
  - Has a `status` (only `published` exams can be taken), `duration_minutes`, `max_attempts` and pass marks.
  - An optional `start_datetime`/`end_datetime` window.
- **`ExamAttempt`** and **`ExamResult`**: scored attempts and the per-question breakdown.

## Rules: `services.py`
- **Window:** `exam_availability` returns `open`, `not_open_yet`, `closed` or `not_published`.
  - Starting outside the window fails with `409` and a `code` saying why (`not_open_yet`, `closed`, `max_attempts`, ...).
  - At submit, the attempt must have *started* inside the window. A student who started in time can finish after the window closes.
- **Questions stay hidden.** The exam detail returns no questions unless the caller has an in-progress, unexpired attempt.
  - Randomized exams save the seed and question order in each new attempt's snapshot. Resuming uses the saved order.
  - Students can review correct answers after submission when the exam releases grades and enables answer review. Older attempts without snapshots retain their recorded grades and totals.
- Grading and analytics use the attempt's recorded questions and grading breakdown where available.

Endpoints: see [docs/API_ROUTES.md](../docs/API_ROUTES.md#apiexams). That file is generated from the URLconf, so it is always current.
