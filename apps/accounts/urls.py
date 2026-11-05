from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from apps.accounts.views import CurrentUserView, TokenCreateView, TokenRevokeView

app_name = "accounts"

urlpatterns = [
    path(
        "accounts/login/",
        LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path(
        "accounts/logout/",
        LogoutView.as_view(next_page="accounts:login"),
        name="logout",
    ),
    path("api/v1/auth/token/", TokenCreateView.as_view(), name="token-create"),
    path("api/v1/auth/me/", CurrentUserView.as_view(), name="current-user"),
    path("api/v1/auth/token/revoke/", TokenRevokeView.as_view(), name="token-revoke"),
]
