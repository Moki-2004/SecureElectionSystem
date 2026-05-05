from django.contrib import admin
from django import forms
from django.utils import timezone

from .models import Election, Candidate

class ElectionAdminForm(forms.ModelForm):
    class Meta:
        model = Election
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate().isoformat()
        start_widget = self.fields['start_time'].widget
        start_widget.attrs['min'] = today

        for widget in getattr(start_widget, 'widgets', [start_widget]):
            input_type = getattr(widget, 'input_type', '')
            if input_type == 'date':
                widget.attrs['min'] = today

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        now = timezone.now()

        if start_time and start_time < now:
            self.add_error('start_time', 'Election start time must be from now onward.')

        if start_time and end_time and end_time <= start_time:
            self.add_error('end_time', 'Election end time must be after the start time.')

        return cleaned_data

class CandidateInline(admin.TabularInline):
    model = Candidate
    extra = 1
    fields = ('name', 'party', 'photo')

@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    form = ElectionAdminForm
    list_display = ('name', 'start_time', 'end_time', 'is_active', 'vote_time_limit')
    list_editable = ('is_active', 'vote_time_limit')
    filter_horizontal = ('eligible_voters',)
    inlines = [CandidateInline]

    def save_model(self, request, obj, form, change):
        if obj.is_active:
            was_inactive = not change
            if change:
                old_obj = Election.objects.filter(pk=obj.pk).first()
                was_inactive = old_obj is not None and not old_obj.is_active

            if was_inactive:
                obj.start_time = timezone.now()

        super().save_model(request, obj, form, change)

@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('name', 'party', 'election')
    list_filter = ('election',)
    search_fields = ('name', 'party')
