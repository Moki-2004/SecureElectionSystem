from django.db import models

class Election(models.Model):
    name = models.CharField(max_length=100)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_active = models.BooleanField(default=False)

    # 🔐 PROCTORING CONTROL
    vote_time_limit = models.IntegerField(
        default=120,
        help_text="Voting time limit in seconds"
    )
    eligible_voters = models.ManyToManyField(
        'users.Voter',
        blank=True,
        related_name='eligible_elections',
        help_text='If set, only these voters may vote in the election.'
    )

    def __str__(self):
        return self.name

    def is_voter_eligible(self, voter):
        if not self.eligible_voters.exists():
            return True
        return self.eligible_voters.filter(pk=voter.pk).exists()

class Candidate(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    party = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='candidates/')

    def __str__(self):
        return self.name
