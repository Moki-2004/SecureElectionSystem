from django.contrib import admin
from .models import ProctoringLog

# Register your models here.


@admin.register(ProctoringLog)
class ProctoringLogAdmin(admin.ModelAdmin):
    list_display = ('voter', 'violation_type', 'timestamp', 'blocked')
    list_filter = ('violation_type', 'blocked')
    search_fields = ('voter__voter_id',)

def violation_type(self, obj):
    return obj.violation_type
violation_type.admin_order_field = 'violation_type'
violation_type.short_description = 'Violation'
