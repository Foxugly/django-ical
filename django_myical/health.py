"""Lightweight health endpoint for external monitoring (UptimeRobot).

Checks DB connectivity only: 200 {"status":"ok"} when a trivial query succeeds,
503 {"status":"degraded"} otherwise. Public, no auth — safe to expose.
"""

from django.db import connection
from django.http import JsonResponse


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # noqa: BLE001 — any DB error means unhealthy
        return JsonResponse({"status": "degraded", "db": "error"}, status=503)
    return JsonResponse({"status": "ok", "db": "ok"})
