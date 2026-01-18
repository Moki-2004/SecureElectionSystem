from django.urls import path
from .views import voter_login

urlpatterns = [
    path('voter-login/', voter_login),
]
