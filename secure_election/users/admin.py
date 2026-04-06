from django.contrib import admin
from django.utils.html import format_html
from .models import Voter

@admin.register(Voter)
class VoterAdmin(admin.ModelAdmin):
    list_display = ('voter_id', 'user', 'has_voted', 'enroll_face_button')

    def enroll_face_button(self, obj):
        if obj.face_image:
            return format_html(
                '<span style="color: green;">Enrolled</span>'
            )
        return format_html(
            '<a class="button" href="/admin/enroll-face/{}/">Enroll Face</a>',
            obj.id
        )

    enroll_face_button.short_description = "Face Enrollment"
