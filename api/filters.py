# File: health_project/api/filters.py
import django_filters
from django.contrib.auth import get_user_model
from data.models import TestResult, Analyte, TestType, MedicalTestSubmission

User = get_user_model()

class TestResultExportFilter(django_filters.FilterSet):
    """
    FilterSet for TestResult model for data export.
    Allows filtering by analyte, user, test date range, and test type.
    """
    analyte_id = django_filters.UUIDFilter(field_name='analyte__id', label='Analyte ID')
    analyte_name = django_filters.CharFilter(field_name='analyte__name', lookup_expr='icontains', label='Analyte Name (Primary)')
    user_id = django_filters.ModelChoiceFilter(
        field_name='submission__user',
        queryset=User.objects.all(), # Admins can filter by any user
        label='User ID'
    )
    test_date_after = django_filters.DateFilter(field_name='submission__test_date', lookup_expr='gte', label='Test Date After (YYYY-MM-DD)')
    test_date_before = django_filters.DateFilter(field_name='submission__test_date', lookup_expr='lte', label='Test Date Before (YYYY-MM-DD)')
    test_type_id = django_filters.ModelChoiceFilter(
        field_name='submission__test_type',
        queryset=TestType.objects.all(),
        label='Test Type ID'
    )
    submission_id = django_filters.ModelChoiceFilter(
        field_name='submission',
        queryset=MedicalTestSubmission.objects.all(),
        label='Submission ID'
    )


    class Meta:
        model = TestResult
        fields = [
            'analyte_id', 
            'analyte_name',
            'user_id', 
            'test_date_after', 
            'test_date_before', 
            'test_type_id',
            'submission_id',
        ]

# You can add other FilterSets here for other models later
# class AnalyteExportFilter(django_filters.FilterSet):
#     name = django_filters.CharFilter(lookup_expr='icontains')
#     class Meta:
#         model = Analyte
#         fields = ['name']

# class HealthSummaryExportFilter(django_filters.FilterSet):
#     user_id = django_filters.ModelChoiceFilter(field_name='user', queryset=User.objects.all())
#     created_at_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
#     created_at_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
#     is_confirmed = django_filters.BooleanFilter()
#     class Meta:
#         model = HealthSummary
#         fields = ['user_id', 'created_at_after', 'created_at_before', 'is_confirmed']
