# health_project/api/filters.py
import django_filters
from django.contrib.auth import get_user_model
from data.models import TestResult, Analyte, TestType, MedicalTestSubmission, HealthSummary

User = get_user_model()

class TestResultExportFilter(django_filters.FilterSet):
    analyte_id = django_filters.UUIDFilter(field_name='analyte__id', label='Analyte ID')
    analyte_name = django_filters.CharFilter(field_name='analyte__name', lookup_expr='icontains', label='Analyte Name (Primary)')
    # user_id БЫЛ УДАЛЕН
    test_date_after = django_filters.DateFilter(field_name='submission__test_date', lookup_expr='gte', label='Test Date After (YYYY-MM-DD)')
    test_date_before = django_filters.DateFilter(field_name='submission__test_date', lookup_expr='lte', label='Test Date Before (YYYY-MM-DD)')
    test_type_id = django_filters.ModelChoiceFilter(
        field_name='submission__test_type',
        queryset=TestType.objects.all(),
        label='Test Type ID',
        to_field_name='id'
    )
    submission_id = django_filters.ModelChoiceFilter(
        field_name='submission',
        queryset=MedicalTestSubmission.objects.all(),
        label='Submission ID',
        to_field_name='id'
    )

    class Meta:
        model = TestResult
        fields = [
            'analyte_id', 
            'analyte_name',
            # 'user_id', # УДАЛЕНО ИЗ СПИСКА ПОЛЕЙ
            'test_date_after', 
            'test_date_before', 
            'test_type_id',
            'submission_id',
        ]

class HealthSummaryExportFilter(django_filters.FilterSet):
    # user_id БЫЛ УДАЛЕН
    created_at_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte', label='Summary Created After (YYYY-MM-DD or champignons-MM-DDTHH:MM)')
    created_at_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte', label='Summary Created Before (YYYY-MM-DD or champignons-MM-DDTHH:MM)')
    is_confirmed = django_filters.BooleanFilter(field_name='is_confirmed', label='Is Confirmed')
    
    class Meta:
        model = HealthSummary
        fields = [
            # 'user_id', # УДАЛЕНО ИЗ СПИСКА ПОЛЕЙ
            'created_at_after',
            'created_at_before',
            'is_confirmed',
        ]