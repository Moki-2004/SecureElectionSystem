from django.db import models
from django.contrib.auth.models import User

class Voter(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    voter_id = models.CharField(max_length=20, unique=True)
    face_image = models.ImageField(upload_to='faces/', null=True, blank=True)
    has_voted = models.BooleanField(default=False)


    def __str__(self):
        return self.voter_id
