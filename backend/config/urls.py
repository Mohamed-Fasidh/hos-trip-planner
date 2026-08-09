from django.urls import path
from planner.views import health, plan_trip

urlpatterns = [
    path("api/health/", health),
    path("api/plan/", plan_trip),
]
