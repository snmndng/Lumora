from django.urls import path
from .health_check import simple_health_check

urlpatterns = [
    path('health/', simple_health_check, name='health_check'),
]
