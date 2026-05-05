from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
        ('elections', '0003_election_vote_time_limit'),
    ]

    operations = [
        migrations.AddField(
            model_name='election',
            name='eligible_voters',
            field=models.ManyToManyField(
                blank=True,
                help_text='If set, only these voters may vote in the election.',
                related_name='eligible_elections',
                to='users.Voter',
            ),
        ),
    ]
