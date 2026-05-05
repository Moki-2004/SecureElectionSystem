from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from elections.models import Candidate, Election
from secure_election.utils.encryption import encrypt_vote
from users.models import Voter

from .models import Vote
from .views import RESULTS_ELECTION_SESSION_KEY, VOTING_ELECTION_SESSION_KEY, hash_receipt_token


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
            election=election,
            candidate=candidate_one,
            encrypted_candidate=encrypt_vote(str(candidate_one.id)),
        )
        Vote.objects.create(
            voter=voter_two,
            election=election,
            candidate=candidate_one,
            encrypted_candidate=encrypt_vote(str(candidate_one.id)),
        )
        Vote.objects.create(
            voter=voter_three,
            election=election,
            candidate=candidate_two,
            encrypted_candidate=encrypt_vote(str(candidate_two.id)),
        )

        response = self.client.get(f'/results/data/?election_id={election.id}')

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
            election=election,
            candidate=candidate_one,
            encrypted_candidate=encrypt_vote(str(candidate_one.id)),
        )
        Vote.objects.create(
            voter=voter_two,
            election=election,
            candidate=candidate_two,
            encrypted_candidate=encrypt_vote(str(candidate_two.id)),
        )

        response = self.client.get(f'/results/data/?election_id={election.id}')

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
        session[VOTING_ELECTION_SESSION_KEY] = self.election.id
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
            election=self.election,
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

    def test_vote_page_blocks_ineligible_voter_for_selected_election(self):
        ineligible_user = User.objects.create_user(username='voter5', password='pass12345')
        ineligible_voter = Voter.objects.create(
            user=ineligible_user,
            voter_id='V005',
            face_image='faces/voter5.jpg',
            has_voted=False,
        )
        eligible_voter = Voter.objects.create(
            user=User.objects.create_user(username='voter6', password='pass12345'),
            voter_id='V006',
            face_image='faces/voter6.jpg',
            has_voted=False,
        )
        self.election.eligible_voters.add(eligible_voter)

        session = self.client.session
        session['face_verified'] = True
        session[VOTING_ELECTION_SESSION_KEY] = self.election.id
        session.save()
        self.client.force_login(ineligible_user)

        response = self.client.post('/vote/', {'candidate': str(self.candidate.id)})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'vote.html')
        self.assertContains(response, 'You are not eligible for this election.')
        self.assertEqual(Vote.objects.filter(voter=ineligible_voter).count(), 0)

    def test_ineligible_voter_cannot_see_candidate_actions(self):
        eligible_voter = Voter.objects.create(
            user=User.objects.create_user(username='eligible_for_actions', password='pass12345'),
            voter_id='ACTION-ELIGIBLE',
            face_image='faces/action-eligible.jpg',
            has_voted=False,
        )
        self.election.eligible_voters.add(eligible_voter)

        session = self.client.session
        session['face_verified'] = True
        session[VOTING_ELECTION_SESSION_KEY] = self.election.id
        session.save()
        self.client.force_login(self.user)

        response = self.client.get('/vote/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You are not eligible for this election.')
        self.assertNotContains(response, self.candidate.name)
        self.assertNotContains(response, 'Submit Vote')
        self.assertContains(response, 'Choose another election')

    def test_results_selection_does_not_create_voting_context(self):
        session = self.client.session
        session['face_verified'] = True
        session[RESULTS_ELECTION_SESSION_KEY] = self.election.id
        session.save()
        self.client.force_login(self.user)

        response = self.client.get('/vote/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/vote-entry/')
        self.assertFalse(Vote.objects.filter(voter=self.voter).exists())

    def test_vote_page_query_string_does_not_create_voting_context(self):
        session = self.client.session
        session['face_verified'] = True
        session.save()
        self.client.force_login(self.user)

        response = self.client.get(f'/vote/?election_id={self.election.id}')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/vote-entry/')
        self.assertNotIn(VOTING_ELECTION_SESSION_KEY, self.client.session)

    def test_vote_entry_rejects_ineligible_selection_before_face_auth(self):
        eligible_voter = Voter.objects.create(
            user=User.objects.create_user(username='eligible_voter', password='pass12345'),
            voter_id='ELIGIBLE',
            face_image='faces/eligible.jpg',
            has_voted=False,
        )
        self.election.eligible_voters.add(eligible_voter)
        self.client.force_login(self.user)

        response = self.client.post('/vote-entry/', {'election_id': str(self.election.id)})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'select_election.html')
        self.assertContains(response, 'You are not eligible for this election.')
        self.assertNotIn(VOTING_ELECTION_SESSION_KEY, self.client.session)

    def test_vote_entry_only_lists_eligible_elections(self):
        other_election = Election.objects.create(
            name='Ineligible Election',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=1),
            is_active=True,
        )
        other_election.eligible_voters.add(Voter.objects.create(
            user=User.objects.create_user(username='other_eligible', password='pass12345'),
            voter_id='OTHER-ELIGIBLE',
            face_image='faces/other-eligible.jpg',
            has_voted=False,
        ))
        self.election.eligible_voters.add(self.voter)
        self.client.force_login(self.user)

        response = self.client.get('/vote-entry/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.election.name)
        self.assertNotContains(response, other_election.name)

    def test_vote_entry_shows_election_selector_before_face_registration(self):
        user_without_face = User.objects.create_user(username='no_face', password='pass12345')
        voter_without_face = Voter.objects.create(
            user=user_without_face,
            voter_id='NO-FACE',
            has_voted=False,
        )
        self.election.eligible_voters.add(voter_without_face)
        self.client.force_login(user_without_face)

        response = self.client.get('/vote-entry/')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'select_election.html')
        self.assertContains(response, self.election.name)

    def test_vote_entry_redirects_without_face_after_election_selection(self):
        user_without_face = User.objects.create_user(username='no_face_after_select', password='pass12345')
        voter_without_face = Voter.objects.create(
            user=user_without_face,
            voter_id='NO-FACE-SELECTED',
            has_voted=False,
        )
        self.election.eligible_voters.add(voter_without_face)
        self.client.force_login(user_without_face)

        response = self.client.post('/vote-entry/', {'election_id': str(self.election.id)})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/face-register/')
        self.assertEqual(self.client.session[VOTING_ELECTION_SESSION_KEY], self.election.id)
