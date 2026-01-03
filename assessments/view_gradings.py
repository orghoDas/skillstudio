from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

from .models import Submission, Assignment
from .grading_services import (
    grade_submission,
    grade_submission_with_rubric
)


class GradeSingleSubmissionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, submission_id):
        submission = get_object_or_404(Submission, id=submission_id)
        course = submission.assignment.lesson.module.course

        if course.instructor != request.user:
            raise PermissionDenied("Instructor access only.")

        score = request.data.get("score")
        feedback = request.data.get("feedback", "")

        grade_submission(submission, score, feedback)

        return Response({"status": "graded"})


class GradeWithRubricView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, submission_id):
        submission = get_object_or_404(Submission, id=submission_id)
        course = submission.assignment.lesson.module.course

        if course.instructor != request.user:
            raise PermissionDenied("Instructor access only.")

        rubric_scores = request.data.get("scores", {})
        feedback = request.data.get("feedback", "")

        grade_submission_with_rubric(
            submission,
            rubric_scores,
            feedback
        )

        return Response({"status": "graded_with_rubric"})


class BulkGradeAssignmentsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        assignment = get_object_or_404(Assignment, id=assignment_id)
        course = assignment.lesson.module.course

        if course.instructor != request.user:
            raise PermissionDenied("Instructor access only.")

        payload = request.data.get("grades", [])
        graded = 0

        for item in payload:
            submission = Submission.objects.filter(
                assignment=assignment,
                user_id=item["user_id"]
            ).first()

            if not submission:
                continue

            grade_submission(
                submission,
                item["score"],
                item.get("feedback", "")
            )
            graded += 1

        return Response({
            "graded_count": graded
        })
