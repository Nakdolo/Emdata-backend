# ==============================================================================
# Файл: api/urls.py
# Описание: URL-маршруты для API приложения.
# ==============================================================================

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Импортируем стандартное представление для регистрации
from dj_rest_auth.registration.views import RegisterView
# Импортируем НАШЕ кастомное представление для верификации
from .views import CustomVerifyEmailAPIView # <-- Импортируем наше представление

# Импортируем наши представления API
from .views import (
    AnalyteHistoryAPIView,
    AnalyteListAPIView,
    UserSubmissionsListAPIView,
    # UserDetailAPIView, # Этот путь предоставляется dj_rest_auth.urls
)

# router = DefaultRouter()
# router.register(...) # Если есть ViewSets

urlpatterns = [
    # path('', include(router.urls)),

    # --- URL для регистрации и верификации ---
    # Используем стандартный RegisterView
    # --- ИСПОЛЬЗУЕМ НАШЕ КАСТОМНОЕ ПРЕДСТАВЛЕНИЕ ---
    # Путь будет /api/auth/registration/verify-email/
    # (т.к. api/urls.py подключен с префиксом /api/ в главном urls.py)
    path('registration/verify-email/', CustomVerifyEmailAPIView.as_view(), name='rest_verify_email'),
    # -------------------------------------------

    # Эндпоинт для получения списка всех аналитов (/api/analytes/)
    path('analytes/', AnalyteListAPIView.as_view(), name='analyte-list-api'),

    # Эндпоинт для получения истории конкретного анализа (/api/analytes/<id>/history/)
    path('analytes/<str:analyte_identifier>/history/', AnalyteHistoryAPIView.as_view(), name='analyte-history-api'),

    # Эндпоинт для получения списка загрузок пользователя (/api/submissions/)
    path('submissions/', UserSubmissionsListAPIView.as_view(), name='submission-list-api'),

]
