from django.contrib.auth.models import User
from django.test import TestCase

from voting.views import VOTING_ELECTION_SESSION_KEY


class VoterLoginFlowTests(TestCase):
    def test_voter_login_defaults_to_election_selection(self):
        User.objects.create_user(username='flow_voter', password='pass12345')

        response = self.client.post('/voter-login/', {
            'username': 'flow_voter',
            'password': 'pass12345',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/vote-entry/')

    def test_voter_login_clears_stale_voting_context(self):
        User.objects.create_user(username='fresh_voter', password='pass12345')
        session = self.client.session
        session['face_verified'] = True
        session[VOTING_ELECTION_SESSION_KEY] = 99
        session.save()

        self.client.post('/voter-login/', {
            'username': 'fresh_voter',
            'password': 'pass12345',
        })

        self.assertNotIn('face_verified', self.client.session)
        self.assertNotIn(VOTING_ELECTION_SESSION_KEY, self.client.session)
