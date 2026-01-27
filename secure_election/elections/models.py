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

    def __str__(self):
        return self.name

class Candidate(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    party = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='candidates/')

    def __str__(self):
        return self.name
