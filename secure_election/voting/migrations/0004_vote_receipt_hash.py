from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voting', '0003_vote_encrypted_candidate'),
    ]

    operations = [
        migrations.AddField(
            model_name='vote',
            name='receipt_hash',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
    ]
