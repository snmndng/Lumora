from django.urls import path
from . import views

app_name = 'mpesa_plugin'

urlpatterns = [
    path('callback/', views.mpesa_callback, name='mpesa_callback'),
    path('timeout/', views.mpesa_timeout, name='mpesa_timeout'),
    path('status/', views.mpesa_status, name='mpesa_status'),
]
