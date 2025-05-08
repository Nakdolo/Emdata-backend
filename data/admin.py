from django.contrib import admin
from .models import HealthSummary, TestType, MedicalTestSubmission, Analyte, TestResult

@admin.register(TestType)
class TestTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Analyte)
class AnalyteAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit', 'name_en', 'name_ru', 'name_kk', 'abbreviations')
    search_fields = ('name', 'name_en', 'name_ru', 'name_kk', 'abbreviations')
    list_filter = ('unit',)
    fieldsets = (
        (None, {'fields': ('name', 'unit', 'description')}),
        ('Localization & Aliases', {'fields': ('name_en', 'name_ru', 'name_kk', 'abbreviations')}),
    )

class TestResultInline(admin.TabularInline):
    model = TestResult
    fields = ('analyte', 'value', 'value_numeric', 'unit', 'reference_range', 'is_abnormal')
    readonly_fields = ('analyte', 'value', 'value_numeric', 'unit', 'reference_range', 'is_abnormal', 'extracted_at')
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(MedicalTestSubmission)
class MedicalTestSubmissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_email', 'test_type', 'submission_date', 'test_date', 'processing_status', 'result_count')
    list_filter = ('processing_status', 'test_type', 'submission_date')
    search_fields = ('user__email', 'id', 'uploaded_file')
    readonly_fields = ('id', 'user', 'submission_date', 'created_at', 'updated_at', 'extracted_text', 'processing_details')
    list_select_related = ('user', 'test_type')
    inlines = [TestResultInline]

    fieldsets = (
        (None, {'fields': ('user', 'submission_date')}),
        ('Test Info', {'fields': ('test_type', 'test_date', 'notes', 'uploaded_file')}),
        ('Processing', {'fields': ('processing_status', 'processing_details', 'extracted_text')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'

    def result_count(self, obj):
        return obj.results.count()
    result_count.short_description = 'Results'

@admin.register(HealthSummary)
class HealthSummaryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at', 'is_confirmed', 'ai_suggested_diagnosis')
    list_filter = ('is_confirmed', 'created_at')
    search_fields = ('user__email', 'ai_suggested_diagnosis', 'confirmed_diagnosis')
    readonly_fields = (
        'user', 'created_at', 'symptoms_prompt', 'analyte_data_snapshot',
        'ai_raw_response', 'ai_summary', 'ai_key_findings', 'ai_detailed_breakdown',
        'ai_suggested_diagnosis', 'is_confirmed', 'confirmed_diagnosis',
        'confirmed_by', 'confirmed_at'
    )
    fieldsets = (
        (None, {'fields': ('user', 'created_at')}),
        ('Input', {'fields': ('symptoms_prompt', 'analyte_data_snapshot')}),
        ('AI Output', {'fields': (
            'ai_summary', 'ai_suggested_diagnosis',
            'ai_key_findings', 'ai_detailed_breakdown', 'ai_raw_response'
        )}),
        ('Confirmation', {'fields': ('is_confirmed', 'confirmed_diagnosis', 'confirmed_by', 'confirmed_at')}),
    )
