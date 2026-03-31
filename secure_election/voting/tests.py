from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from elections.models import Candidate, Election
from secure_election.utils.encryption import encrypt_vote
from users.models import Voter

from .models import Vote


class PublicResultsDataTests(TestCase):
    def test_results_data_returns_live_totals_and_winner(self):
        election = Election.objects.create(
            name='Student Council',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=1),
            is_active=True,
        )
        candidate_one = Candidate.objects.create(
            election=election,
            name='Alice',
            party='Unity',
            photo='candidates/alice.jpg',
        )
        candidate_two = Candidate.objects.create(
            election=election,
            name='Bob',
            party='Progress',
            photo='candidates/bob.jpg',
        )

        voter_one = Voter.objects.create(
            user=User.objects.create_user(username='voter1', password='pass12345'),
            voter_id='V001',
            has_voted=True,
        )
        voter_two = Voter.objects.create(
            user=User.objects.create_user(username='voter2', password='pass12345'),
            voter_id='V002',
            has_voted=True,
        )
        voter_three = Voter.objects.create(
            user=User.objects.create_user(username='voter3', password='pass12345'),
            voter_id='V003',
            has_voted=True,
        )

        Vote.objects.create(
            voter=voter_one,
            candidate=candidate_one,
            encrypted_candidate=encrypt_vote(str(candidate_one.id)),
        )
        Vote.objects.create(
            voter=voter_two,
            candidate=candidate_one,
            encrypted_candidate=encrypt_vote(str(candidate_one.id)),
        )
        Vote.objects.create(
            voter=voter_three,
            candidate=candidate_two,
            encrypted_candidate=encrypt_vote(str(candidate_two.id)),
        )

        response = self.client.get('/results/data/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'results': [
                {'candidate_id': candidate_one.id, 'name': 'Alice', 'votes': 2},
                {'candidate_id': candidate_two.id, 'name': 'Bob', 'votes': 1},
            ],
            'winner': 'Alice',
            'total_votes': 3,
        })
