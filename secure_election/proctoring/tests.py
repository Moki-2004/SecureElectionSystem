from django.contrib.auth.models import User
from django.test import TestCase

from users.models import Voter
from voting.views import VOTING_ELECTION_SESSION_KEY


class FaceFlowTests(TestCase):
    def test_face_register_with_existing_face_returns_to_election_selection_without_context(self):
        user = User.objects.create_user(username='registered_face', password='pass12345')
        Voter.objects.create(
            user=user,
            voter_id='REGISTERED-FACE',
            face_image='faces/registered.jpg',
        )
        self.client.force_login(user)

        response = self.client.get('/face-register/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/vote-entry/')

    def test_face_register_with_existing_face_continues_to_auth_with_context(self):
        user = User.objects.create_user(username='registered_with_context', password='pass12345')
        Voter.objects.create(
            user=user,
            voter_id='REGISTERED-CONTEXT',
            face_image='faces/registered-context.jpg',
        )
        session = self.client.session
        session[VOTING_ELECTION_SESSION_KEY] = 1
        session.save()
        self.client.force_login(user)

        response = self.client.get('/face-register/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/face-auth/')

    def test_face_auth_without_face_after_selection_redirects_to_registration(self):
        user = User.objects.create_user(username='auth_without_face', password='pass12345')
        Voter.objects.create(
            user=user,
            voter_id='AUTH-NO-FACE',
        )
        session = self.client.session
        session[VOTING_ELECTION_SESSION_KEY] = 1
        session.save()
        self.client.force_login(user)

        response = self.client.get('/face-auth/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/face-register/')
