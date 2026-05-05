import django.db.models.deletion
from django.db import migrations, models


def populate_vote_election(apps, schema_editor):
    Vote = apps.get_model('voting', 'Vote')
    Candidate = apps.get_model('elections', 'Candidate')

    for vote in Vote.objects.all():
        if vote.candidate_id:
            candidate = Candidate.objects.filter(pk=vote.candidate_id).first()
            if candidate:
                vote.election_id = candidate.election_id
                vote.save(update_fields=['election_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('elections', '0003_election_vote_time_limit'),
        ('voting', '0004_vote_receipt_hash'),
    ]

    operations = [
        migrations.AddField(
            model_name='vote',
            name='election',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='elections.Election',
            ),
        ),
        migrations.RunPython(populate_vote_election, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='vote',
            name='election',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to='elections.Election',
            ),
        ),
        migrations.AlterField(
            model_name='vote',
            name='voter',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to='users.Voter',
            ),
        ),
        migrations.AddConstraint(
            model_name='vote',
            constraint=models.UniqueConstraint(
                fields=['voter', 'election'],
                name='unique_vote_per_election',
            ),
        ),
    ]
