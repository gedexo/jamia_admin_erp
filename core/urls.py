# This urls.py is for main app (non-API) views only.
# API endpoints are defined separately in api_urls.py.
from . import views
from django.urls import path

app_name = "core"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/read/<int:pk>/', views.notification_read_and_redirect, name='notification_read_and_redirect'),
    path('notifications/mark_read/<int:pk>/', views.notification_mark_read, name='notification_mark_read'),
    path("notifications/clear-all/", views.notification_clear_all, name="notification_clear_all"),

]
