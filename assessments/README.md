# assessments

Lesson-level quizzes (multiple choice only).

## Models
- **`Quiz`**: one per quiz lesson.
  - A new quiz is a **draft** (`is_published=False`) until the instructor publishes it.
  - `total_marks` always equals the sum of the questions' marks. `signals.py` recomputes it whenever a question is saved or deleted, from any code path.
  - `max_attempts` defaults to 3; `null` means unlimited.
  - `time_limit_minutes` is optional.
- **`QuizQuestion`** (`difficulty` is `easy`, `medium` or `hard`) and **`QuestionOption`**. Each question has exactly one correct option.
- **`QuizAttempt`**:
  - Numbered per user (`attempt_number`), with at most one attempt open at a time (database constraints).
  - Stores a snapshot of the questions and marks, so later edits never change past grades.

## Rules: `services.py`
- Only a published quiz with questions can block lesson completion (`Quiz.counts_for_completion`).
- `start_quiz_attempt` behaves differently by state:
  - If an attempt is still open, it resumes that attempt.
  - If the open attempt has expired, it grades it first.
  - If the student has passed or used every attempt, it refuses.
- `submit_quiz_attempt` ignores answers that arrive after the time limit plus `QUIZ_SUBMIT_GRACE_SECONDS`. The server enforces the limit; the browser timer is cosmetic.
- Questions can't be replaced once any attempt exists. Make a new quiz instead.
- Analytics (`analytics.py`) count finished attempts only. The course owner or a platform admin can read them.

Endpoints: see [docs/API_ROUTES.md](../docs/API_ROUTES.md#apiassessments). That file is generated from the URLconf, so it is always current.
