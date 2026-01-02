from django.urls import path
from .views import (
    QuizDetailView,
    StartQuizView,
    SubmitQuizView,
    AssignmentDetailView,
    SubmitAssignmentView
)

from .view_analytics import (
    InstructorAssessmentOverviewView,
    QuizQuestionAnalyticsView
)

from .view_gradings import (
    GradeSingleSubmissionView,
    GradeWithRubricView,
    BulkGradeAssignmentsView
)

from .views_attempt import (
    StartQuizAttemptView,
    SubmitQuizAttemptView,
    SubmitQuizAnswerView
)


urlpatterns = [
    # Quiz
    path("quiz/lesson/<int:lesson_id>/", QuizDetailView.as_view()),
    path("quiz/<int:quiz_id>/start/", StartQuizView.as_view()),
    path("quiz/attempt/<int:attempt_id>/submit/", SubmitQuizView.as_view()),

    # Assignment
    path("assignment/lesson/<int:lesson_id>/", AssignmentDetailView.as_view()),
    path("assignment/<int:assignment_id>/submit/", SubmitAssignmentView.as_view()),

    # Analytics
    path("analytics/course/<int:course_id>/overview/", InstructorAssessmentOverviewView.as_view()), 
    path("analytics/quiz/<int:quiz_id>/questions/", QuizQuestionAnalyticsView.as_view()),

    # Grading
    path("grading/submission/<int:submission_id>/grade/", GradeSingleSubmissionView.as_view()),
    path("grading/submission/<int:submission_id>/grade_with_rubric/", GradeWithRubricView.as_view()),
    path("grading/assignment/<int:assignment_id>/bulk_grade/", BulkGradeAssignmentsView.as_view()),

    # Quiz Attempts
    path("quiz/<int:quiz_id>/attempt/start/", StartQuizAttemptView.as_view()),
    path("quiz/attempt/<int:attempt_id>/submit/", SubmitQuizAttemptView.as_view()),
    path("quiz/attempt/<int:attempt_id>/answer/submit/", SubmitQuizAnswerView.as_view()),
]
