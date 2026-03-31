from django.urls import path
from .views import vote_entry, vote_page, public_results, public_results_data

urlpatterns = [
    path('vote-entry/', vote_entry),
    path('vote/', vote_page),
    path('results/', public_results),
    path('results/data/', public_results_data),
]
