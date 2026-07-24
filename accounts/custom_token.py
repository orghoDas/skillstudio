from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken, TokenError

from .cookies import set_jwt_cookies


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except AuthenticationFailed:
            # Customize the error message for wrong password. Raise with a plain
            # string so DRF's exception handler returns a proper JSON detail.
            raise AuthenticationFailed("Incorrect email or password.")


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            set_jwt_cookies(
                response, response.data.get("access"), response.data.get("refresh")
            )
        return response


class CookieTokenRefreshView(TokenRefreshView):
    """Refresh using the refresh token from the request body OR the cookie,
    and write the rotated access (and refresh) back as httpOnly cookies."""

    def post(self, request, *args, **kwargs):
        refresh = request.data.get("refresh") or request.COOKIES.get(
            settings.JWT_AUTH_REFRESH_COOKIE
        )
        if not refresh:
            return Response(
                {"detail": "No refresh token provided."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = self.get_serializer(data={"refresh": refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0])

        response = Response(serializer.validated_data, status=status.HTTP_200_OK)
        set_jwt_cookies(
            response, response.data.get("access"), response.data.get("refresh")
        )
        return response
