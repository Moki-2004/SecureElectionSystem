from django.db import models
from users.models import Voter
from elections.models import Candidate

class Vote(models.Model):
    voter = models.OneToOneField(Voter, on_delete=models.CASCADE)
    encrypted_candidate = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.voter.voter_id
