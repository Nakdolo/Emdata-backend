# ==============================================================================
# Файл: api/urls.py
# Описание: URL-маршруты для API приложения.
# ==============================================================================

from django.urls import path

# Импортируем представления из data.views
from data.views import DownloadSubmissionFileView, DeleteSubmissionView

# Импортируем представления из текущего приложения (api.views)
from .views import (
    CustomVerifyEmailAPIView, 
    AnalyteHistoryAPIView,   
    AnalyteListAPIView,
    UserHealthStatisticsAPIView,      
    UserSubmissionsListAPIView,
    UploadLabResultsAPIView, 
    SubmissionDetailAPIView, 
)

urlpatterns = [
    # --- URL для регистрации и верификации ---
    path('registration/verify-email/', CustomVerifyEmailAPIView.as_view(), name='rest_verify_email'),

    # --- Аналиты ---
    path('analytes/', AnalyteListAPIView.as_view(), name='analyte-list-api'),
    path('analytes/<str:analyte_identifier>/history/', AnalyteHistoryAPIView.as_view(), name='analyte-history-api'),

    # --- Загрузки (Submissions) ---
    # Для загрузки файлов (POST)
    path('upload/', UploadLabResultsAPIView.as_view(), name='upload_lab_results_api'),
    
    # Для списка загрузок пользователя (GET)
    path('submissions/', UserSubmissionsListAPIView.as_view(), name='submission-list-api'),
    
    # Для получения деталей конкретной загрузки (GET)
    # Убедитесь, что SubmissionDetailAPIView в api/views.py обрабатывает GET
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
]
