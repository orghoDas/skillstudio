from django.urls import path
from .views import (
    QuizDetailView,
    StartQuizView,
    SubmitQuizView,
)

from .views_quiz_management import ManageQuizView

from .view_analytics import (
    InstructorAssessmentOverviewView,
    QuizQuestionAnalyticsView
)

from .views_attempt import (
    StartQuizAttemptView,
    SubmitQuizAnswerView
)


urlpatterns = [
    # Quiz
    path("quiz/lesson/<int:lesson_id>/", QuizDetailView.as_view()),
    path("quiz/<int:quiz_id>/start/", StartQuizView.as_view()),
    path("quiz/attempt/<int:attempt_id>/submit/", SubmitQuizView.as_view()),

    # Quiz Management (Instructor)
    path("quiz/lesson/<int:lesson_id>/manage/", ManageQuizView.as_view()),

    # Analytics
    path("analytics/course/<int:course_id>/overview/", InstructorAssessmentOverviewView.as_view()), 
    path("analytics/quiz/<int:quiz_id>/questions/", QuizQuestionAnalyticsView.as_view()),

    # Quiz Attempts
    path("quiz/<int:quiz_id>/attempt/start/", StartQuizAttemptView.as_view()),
    path("quiz/attempt/<int:attempt_id>/answer/submit/", SubmitQuizAnswerView.as_view()),
]
