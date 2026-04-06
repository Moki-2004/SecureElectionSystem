import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import migrations, models


def _cipher():
    secret = getattr(settings, 'VOTE_ENCRYPTION_SECRET', None) or settings.SECRET_KEY
    digest = hashlib.sha256(secret.encode('utf-8')).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_existing_votes(apps, schema_editor):
    Vote = apps.get_model('voting', 'Vote')
    cipher = _cipher()

    for vote in Vote.objects.all():
        if vote.candidate_id and not vote.encrypted_candidate:
            encrypted = cipher.encrypt(str(vote.candidate_id).encode('utf-8')).decode('utf-8')
            vote.encrypted_candidate = encrypted
            vote.save(update_fields=['encrypted_candidate'])


class Migration(migrations.Migration):

    dependencies = [
        ('voting', '0002_alter_vote_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='vote',
            name='encrypted_candidate',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.RunPython(encrypt_existing_votes, migrations.RunPython.noop),
    ]
