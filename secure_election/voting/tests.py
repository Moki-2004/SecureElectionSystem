from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from elections.models import Candidate, Election
from secure_election.utils.encryption import encrypt_vote
from users.models import Voter

from .models import Vote
from .views import hash_receipt_token


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
            'is_tie': False,
            'tied_candidates': [],
            'total_votes': 3,
        })

    def test_results_data_returns_tie_when_top_candidates_have_equal_votes(self):
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
            user=User.objects.create_user(username='tie_voter1', password='pass12345'),
            voter_id='TV001',
            has_voted=True,
        )
        voter_two = Voter.objects.create(
            user=User.objects.create_user(username='tie_voter2', password='pass12345'),
            voter_id='TV002',
            has_voted=True,
        )

        Vote.objects.create(
            voter=voter_one,
            candidate=candidate_one,
            encrypted_candidate=encrypt_vote(str(candidate_one.id)),
        )
        Vote.objects.create(
            voter=voter_two,
            candidate=candidate_two,
            encrypted_candidate=encrypt_vote(str(candidate_two.id)),
        )

        response = self.client.get('/results/data/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'results': [
                {'candidate_id': candidate_one.id, 'name': 'Alice', 'votes': 1},
                {'candidate_id': candidate_two.id, 'name': 'Bob', 'votes': 1},
            ],
            'winner': 'Tie',
            'is_tie': True,
            'tied_candidates': ['Alice', 'Bob'],
            'total_votes': 2,
        })


class VoteReceiptTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='voter4', password='pass12345')
        self.voter = Voter.objects.create(
            user=self.user,
            voter_id='V004',
            face_image='faces/voter4.jpg',
            has_voted=False,
        )
        self.election = Election.objects.create(
            name='College Election',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=1),
            is_active=True,
        )
        self.candidate = Candidate.objects.create(
            election=self.election,
            name='Carol',
            party='Future',
            photo='candidates/carol.jpg',
        )

    def test_vote_submission_creates_hashed_receipt_and_shows_plain_token_once(self):
        session = self.client.session
        session['face_verified'] = True
        session.save()
        self.client.force_login(self.user)

        response = self.client.post('/vote/', {'candidate': str(self.candidate.id)})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'vote_receipt.html')

        vote = Vote.objects.get(voter=self.voter)
        plain_token = response.context['receipt_token']

        self.assertTrue(vote.receipt_hash)
        self.assertNotEqual(vote.receipt_hash, plain_token)
        self.assertEqual(vote.receipt_hash, hash_receipt_token(plain_token))

    def test_verify_receipt_confirms_existing_vote_without_disclosing_choice(self):
        Vote.objects.create(
            voter=self.voter,
            candidate=self.candidate,
            encrypted_candidate=encrypt_vote(str(self.candidate.id)),
            receipt_hash=hash_receipt_token('ABCD-EF12-3456-7890-ABCD-EF12'),
        )

        response = self.client.post('/verify-receipt/', {
            'receipt_token': 'ABCD-EF12-3456-7890-ABCD-EF12',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vote record found.')
        self.assertNotContains(response, self.candidate.name)
