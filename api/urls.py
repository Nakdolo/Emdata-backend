# ==============================================================================
# Файл: api/urls.py
# Описание: URL-маршруты для API приложения.
# ==============================================================================

from django.urls import path

# Импортируем представления из data.views
from data.views import DownloadSubmissionFileView, DeleteSubmissionView

# Импортируем представления из текущего приложения (api.views)
from .views import (
    ConfirmHealthSummaryDiagnosisAPIView,
    CustomVerifyEmailAPIView, 
    AnalyteHistoryAPIView,   
    AnalyteListAPIView,
    GenerateHealthSummaryAPIView,
    HealthSummaryCSVExportAPIView,
    TestResultCSVExportAPIView,
    TestTypeListAPIView,
    UserHealthStatisticsAPIView,      
    UserSubmissionsListAPIView,
    UploadLabResultsAPIView, 
    SubmissionDetailAPIView,
    UserHealthSummariesListAPIView,
)

urlpatterns = [
    # --- URL для регистрации и верификации ---
    path('registration/verify-email/', CustomVerifyEmailAPIView.as_view(), name='rest_verify_email'),

    # --- Аналиты ---
    path('analytes/', AnalyteListAPIView.as_view(), name='analyte-list-api'),
    path('analytes/<str:analyte_identifier>/history/', AnalyteHistoryAPIView.as_view(), name='analyte-history-api'),

    # --- Загрузки (Submissions) ---
    path('upload/', UploadLabResultsAPIView.as_view(), name='upload_lab_results_api'),
    
    # Для списка загрузок пользователя (GET)
    path('submissions/', UserSubmissionsListAPIView.as_view(), name='submission-list-api'),
    
    # Для получения деталей конкретной загрузки (GET)
    path('submissions/<uuid:id>/', SubmissionDetailAPIView.as_view(), name='submission-detail-api'),

    # --- URL для УДАЛЕНИЯ конкретной загрузки (DELETE) ---
    # Используем DeleteSubmissionView из data.views
    # Фронтенд вызывает /api/submission/<submissionId>/delete/
    path('submission/<uuid:submission_id>/delete/', DeleteSubmissionView.as_view(), name='delete_submission_url'),

    # --- URL для СКАЧИВАНИЯ файла через API ---
    # Фронтенд вызывает /api/submission/<submissionId>/download/
    path('submission/<uuid:submission_id>/download/', DownloadSubmissionFileView.as_view(), name='api_submission_download_url'),

        # --- URL для статистики здоровья ---
    path('health-statistics/', UserHealthStatisticsAPIView.as_view(), name='user-health-statistics-api'),
    path('generate-health-summary/', GenerateHealthSummaryAPIView.as_view(), name='generate-health-summary-api'), # <-- НОВЫЙ МАРШРУТ
    path('health-summaries/', UserHealthSummariesListAPIView.as_view(), name='user-health-summaries-list-api'), # <-- NEW URL PATTERN FOR LISTING ALL SUMMARIES
    path('health-summaries/<uuid:summary_id>/confirm/', ConfirmHealthSummaryDiagnosisAPIView.as_view(), name='confirm-health-summary-diagnosis'),


    # --- URL для экспорта в CSV ---
    path('test-types/', TestTypeListAPIView.as_view(), name='api-test-type-list'), # НОВЫЙ МАРШРУТ
    path('export/test-results/csv/', TestResultCSVExportAPIView.as_view(), name='export-test-results-csv'),
    path('export/health-summaries/csv/', HealthSummaryCSVExportAPIView.as_view(), name='export-health-summaries-csv'),]
