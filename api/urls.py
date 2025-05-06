# ==============================================================================
# Файл: api/urls.py
# Описание: URL-маршруты для API приложения.
# Включает URL для загрузки файлов и списка загрузок.
# ==============================================================================

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Импортируем НАШЕ кастомное представление для верификации
from .views import CustomVerifyEmailAPIView, SubmissionDetailAPIView # <-- Импортируем наше представление

# Импортируем наши представления API (включая новые)
from .views import (
    AnalyteHistoryAPIView,
    AnalyteListAPIView,
    UserSubmissionsListAPIView, # Представление для списка загрузок
    UploadLabResultsAPIView, # Представление для загрузки файлов
    # UserDetailAPIView, # Этот путь предоставляется dj_rest_auth.urls
)

# Если у вас есть ViewSets, их можно зарегистрировать здесь
# router = DefaultRouter()
# router.register(r'some_resource', SomeViewSet)

urlpatterns = [
    # Если используете ViewSets, добавьте:
    # path('', include(router.urls)),

    # --- URL для регистрации и верификации (часть allauth) ---
    # Используем наше кастомное представление для верификации
    path('registration/verify-email/', CustomVerifyEmailAPIView.as_view(), name='rest_verify_email'),
    # ---------------------------------------------------------

    # Эндпоинт для получения списка всех аналитов (/api/analytes/)
    path('analytes/', AnalyteListAPIView.as_view(), name='analyte-list-api'),

    # Эндпоинт для получения истории конкретного анализа (/api/analytes/<uuid:analyte_id>/history/)
    # Используем <str:...> или <uuid:...> в зависимости от того, как вы передаете ID аналита
    # В get_analyte в views.py используется логика для UUID или имени/алиаса,
    # поэтому <str:analyte_identifier> более гибкий, но <uuid:analyte_id> точнее, если передаете UUID.
    # Оставляем <str:analyte_identifier> как было в вашем коде.
    path('analytes/<str:analyte_identifier>/history/', AnalyteHistoryAPIView.as_view(), name='analyte-history-api'),

    # --- Эндпоинт для получения списка загрузок пользователя (/api/submissions/) ---
    path('submissions/', UserSubmissionsListAPIView.as_view(), name='submission-list-api'),
    # -------------------------------------------------------------------------------
        # --- Эндпоинт для получения данных ---

    path('submissions/<uuid:id>/', SubmissionDetailAPIView.as_view(), name='submission-detail-api'),

    # --- Эндпоинт для загрузки файлов (/api/upload/) ---
    path('upload/', UploadLabResultsAPIView.as_view(), name='upload-lab-results-api'),
    # ---------------------------------------------------

    # Добавь здесь другие API URLы, если они есть

]
