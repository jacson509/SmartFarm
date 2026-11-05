from django.http import JsonResponse


def api_not_found(request, unmatched=""):
    return JsonResponse(
        {"detail": "Le point de terminaison API demandé n’existe pas."},
        status=404,
    )
