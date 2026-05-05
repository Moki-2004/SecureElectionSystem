from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.test import TestCase
from django.utils import timezone

from .admin import ElectionAdmin, ElectionAdminForm
from .models import Election


class ElectionAdminFormTests(TestCase):
    def test_start_time_cannot_be_in_the_past(self):
        form = ElectionAdminForm(data={
            'name': 'Past Election',
            'start_time_0': (timezone.localdate() - timedelta(days=1)).strftime('%Y-%m-%d'),
            'start_time_1': '10:00:00',
            'end_time_0': (timezone.localdate() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_time_1': '10:00:00',
            'is_active': 'on',
            'vote_time_limit': '120',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('start_time', form.errors)

    def test_end_time_must_be_after_start_time(self):
        start = timezone.now() + timedelta(hours=1)
        form = ElectionAdminForm(data={
            'name': 'Invalid End',
            'start_time_0': start.strftime('%Y-%m-%d'),
            'start_time_1': start.strftime('%H:%M:%S'),
            'end_time_0': start.strftime('%Y-%m-%d'),
            'end_time_1': start.strftime('%H:%M:%S'),
            'is_active': '',
            'vote_time_limit': '120',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('end_time', form.errors)

    def test_start_date_widget_min_is_today(self):
        form = ElectionAdminForm()
        widget = form.fields['start_time'].widget

        self.assertEqual(widget.attrs['min'], timezone.localdate().isoformat())


class ElectionAdminTests(TestCase):
    def test_activating_existing_election_sets_start_time_to_now(self):
        original_start = timezone.now() - timedelta(days=30)
        election = Election.objects.create(
            name='2026 Election',
            start_time=original_start,
            end_time=timezone.now() + timedelta(days=1),
            is_active=False,
        )
        election.is_active = True

        before_save = timezone.now()
        ElectionAdmin(Election, AdminSite()).save_model(None, election, None, change=True)
        after_save = timezone.now()

        election.refresh_from_db()
        self.assertGreaterEqual(election.start_time, before_save)
        self.assertLessEqual(election.start_time, after_save)
