from django.urls import path
from .views import face_register, face_authenticate, log_violation
urlpatterns = [
    path('face-register/', face_register),
    path('face-auth/', face_authenticate),
    path('log-violation/', log_violation),
]
