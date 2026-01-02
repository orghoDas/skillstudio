from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ai_recommender.services import recommend_courses

# Create your views here.
class SkillRecommenderView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        courses = recommend_courses(request.user)

        return Response({
            "recommended_courses": [
                {
                    "id": c.id,
                    "title": c.title,
                    "rating": c.avg_rating,
                }
                for c in courses
            ]
        })

