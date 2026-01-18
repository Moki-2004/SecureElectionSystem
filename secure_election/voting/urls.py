from django.urls import path
from .views import vote_page

urlpatterns = [
    path('vote/', vote_page),
]
