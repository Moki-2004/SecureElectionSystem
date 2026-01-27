from django.db import models
from users.models import Voter

class ProctoringRule(models.Model):
    """
    Admin-configurable rules
    """
    vote_time_limit = models.IntegerField(default=120)  # seconds
    max_warnings = models.IntegerField(default=2)

    def __str__(self):
        return "Proctoring Rules"


class ProctoringLog(models.Model):
    """
    Logs all violations
    """
    VIOLATION_TYPES = [
        ('NO_FACE', 'No Face Detected'),
        ('MULTIPLE_FACES', 'Multiple Faces Detected'),
        ('CAMERA_OFF', 'Camera Tampering'),
        ('FACE_CHANGED', 'Face Changed'),
        ('TIME_EXCEEDED', 'Time Exceeded'),
    ]

    voter = models.ForeignKey(Voter, on_delete=models.CASCADE)
    violation_type = models.CharField(max_length=20, choices=VIOLATION_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)
    blocked = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.voter.voter_id} - {self.violation_type}"
