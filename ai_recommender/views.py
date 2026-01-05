from rest_framework import generics, permissions
from rest_framework.views import APIView
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Recommendation
from .serializers import RecommendationSerializer
from rest_framework.response import Response


class UserRecommendationsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RecommendationSerializer

    def get_queryset(self):
        user = self.request.user
        return Recommendation.objects.filter(user=user, status='active').order_by('-score')


from rest_framework.permissions import IsAdminUser
from django.core.cache import cache
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator


class FeatureFlagView(APIView):
    """Simple feature flag controller for `ai_recommender`."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        enabled = cache.get('ai_recommender_enabled', True)
        return Response({'ai_recommender_enabled': bool(enabled)})

    def post(self, request):
        enabled = request.data.get('enabled')
        if enabled is None:
            return Response({'error': 'missing "enabled" boolean'}, status=400)
        cache.set('ai_recommender_enabled', bool(enabled), None)
        return Response({'ai_recommender_enabled': bool(enabled)})


class RecommendationWidgetView(LoginRequiredMixin, TemplateView):
    """Render a small widget that fetches recommendations via the API."""

    template_name = 'ai_recommender/widget.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_staff'] = bool(self.request.user and self.request.user.is_staff)
        return ctx


@login_required
def recommendations_widget_data(request):
    """Return minimal recommendation list for the logged-in user (session-auth compatible)."""
    qs = Recommendation.objects.filter(user=request.user, status='active').select_related('course').order_by('-score')[:20]
    data = []
    for r in qs:
        data.append({
            'id': r.id,
            'score': float(r.score),
            'reason': r.reason,
            'course': {
                'id': r.course_id,
                'title': getattr(r.course, 'title', '')
            }
        })
    return JsonResponse(data, safe=False)
