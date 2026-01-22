from django.urls import path
from .views import vote_entry, vote_page

urlpatterns = [
    path('vote-entry/', vote_entry),
    path('vote/', vote_page),
]
