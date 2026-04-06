from django.urls import path

from .views import public_results, public_results_data, verify_receipt, vote_entry, vote_page

urlpatterns = [
    path('vote-entry/', vote_entry),
    path('vote/', vote_page),
    path('verify-receipt/', verify_receipt),
    path('results/', public_results),
    path('results/data/', public_results_data),
]
