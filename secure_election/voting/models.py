from django.db import models
from users.models import Voter
from elections.models import Candidate, Election


class Vote(models.Model):
    voter = models.ForeignKey(Voter, on_delete=models.CASCADE)
    election = models.ForeignKey(Election, on_delete=models.CASCADE)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE)
    encrypted_candidate = models.TextField(blank=True, default="")
    receipt_hash = models.CharField(max_length=64, blank=True, default="")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['voter', 'election'],
                name='unique_vote_per_election'
            )
        ]

    def __str__(self):
        return self.voter.voter_id
