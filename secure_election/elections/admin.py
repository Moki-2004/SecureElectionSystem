from django.contrib import admin
from .models import Election, Candidate

admin.site.register(Candidate)

@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'vote_time_limit')
    list_editable = ('is_active', 'vote_time_limit')