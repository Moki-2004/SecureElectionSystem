from django.urls import path
from .views import vote_entry, vote_page, public_results

urlpatterns = [
    path('vote-entry/', vote_entry),
    path('vote/', vote_page),
    path('results/', public_results),  # optional public page
]
