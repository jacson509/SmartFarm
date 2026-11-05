from django.shortcuts import render

# Create your views here.
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class TokenCreateView(ObtainAuthToken):
    """Issue a DRF token after valid username/password authentication."""

    permission_classes = [AllowAny]


class CurrentUserView(APIView):
    """Return a minimal identity document without exposing credentials."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"id": request.user.pk, "username": request.user.get_username()})


class TokenRevokeView(APIView):
    """Revoke only the API token presented on this request."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.auth
        if isinstance(token, Token):
            token.delete()
        return Response({"detail": "Token revoked."}, status=status.HTTP_200_OK)
