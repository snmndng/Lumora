"""
Health check view for Saleor deployment monitoring.
Place this file in: saleor/core/health_check.py
"""
from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError
import redis
from django.conf import settings


def health_check(request):
    """
    Simple health check endpoint that verifies:
    - Application is running
    - Database connection is working
    - Redis connection is working (if configured)
    """
    health_status = {
        "status": "healthy",
        "checks": {}
    }

    # Check database connection
    try:
        db_conn = connections['default']
        db_conn.cursor()
        health_status["checks"]["database"] = "ok"
    except OperationalError as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = f"error: {str(e)}"

    # Check Redis connection (if REDIS_URL is set)
    if hasattr(settings, 'REDIS_URL') and settings.REDIS_URL:
        try:
            redis_client = redis.from_url(settings.REDIS_URL)
            redis_client.ping()
            health_status["checks"]["redis"] = "ok"
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["checks"]["redis"] = f"error: {str(e)}"

    status_code = 200 if health_status["status"] == "healthy" else 503
    return JsonResponse(health_status, status=status_code)


def simple_health_check(request):
    """
    Ultra-simple health check that just returns 200 OK.
    Use this if you want Render to just verify the service is responding.
    """
    return JsonResponse({"status": "ok"}, status=200)
