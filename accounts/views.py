from django.shortcuts import render
from rest_framework import generics, permissions
from .serializers import RegisterSerializer, ProfileSerializer, MeSerializer
from .models import Profile

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .permissions import IsInstructor, IsAdmin

from rest_framework import status
from django.shortcuts import get_object_or_404

from accounts.models import User


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
    

class PromoteToInstructorView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        user.role = User.Role.INSTRUCTOR
        user.save()
        return Response({"message": f"User {user.email} promoted to Instructor."}, status=status.HTTP_200_OK)
    

def login_page(request):
    return render(request, "auth/login.html")


def register_page(request):
    return render(request, "auth/register.html")


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = MeSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = MeSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
