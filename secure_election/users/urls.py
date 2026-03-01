from django.urls import path
from .views import voter_login, voter_logout

urlpatterns = [
    path('voter-login/', voter_login, name='voter_login'),
    path('logout/', voter_logout, name='logout'),
]