from django.conf import settings


def site_state(request):
    return {"DEBUG": settings.DEBUG, "STATE": getattr(settings, "STATE", "")}
