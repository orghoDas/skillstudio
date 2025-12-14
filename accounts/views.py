from django.shortcuts import render
from rest_framework import generics, permissions
from .serializers import RegisterSerializer, ProfileSerializer
from .models import Profile

from rest_framework.views import APIView
from rest_framework.response import Response
from .permissions import IsInstructor


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = (permissions.AllowAny,)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user.profile
    

class InstructorOnlyView(APIView):
    permission_classes = [IsInstructor]

    def get(self, request):
        return Response({"message": "Hello, Instructor!", 'user': request.user.email})