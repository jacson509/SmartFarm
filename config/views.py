from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def home(request):
    """Minimal authenticated landing page until the dashboard phase."""
    return render(request, "registration/home.html")
