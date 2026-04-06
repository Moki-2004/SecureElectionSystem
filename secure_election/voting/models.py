from django.db import models
from users.models import Voter
from elections.models import Candidate


class Vote(models.Model):
    voter = models.OneToOneField(Voter, on_delete=models.CASCADE)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE)
    encrypted_candidate = models.TextField(blank=True, default="")
    receipt_hash = models.CharField(max_length=64, blank=True, default="")
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.voter.voter_id
