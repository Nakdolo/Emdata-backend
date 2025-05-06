# ==============================================================================
# Файл: api/urls.py
# Описание: URL-маршруты для API приложения.
# ==============================================================================

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Импортируем стандартные представления dj-rest-auth
from dj_rest_auth.registration.views import RegisterView, VerifyEmailView
# from dj_rest_auth.registration.views import ResendEmailVerificationView

# Импортируем наши представления API
from .views import (
    AnalyteHistoryAPIView,
    AnalyteListAPIView,
    UserSubmissionsListAPIView,
    UserDetailAPIView,
)

# router = DefaultRouter()
# router.register(...) # Если есть ViewSets

urlpatterns = [
    # path('', include(router.urls)),
     # Эндпоинт для получения информации о текущем пользователе (из dj_rest_auth.urls)
    # /api/auth/user/ - он подключен в главном urls.py

    # Эндпоинт для получения списка всех аналитов
    # /api/analytes/
    path('analytes/', AnalyteListAPIView.as_view(), name='analyte-list-api'),

    # Эндпоинт для получения истории конкретного анализа
    # /api/analytes/<id>/history/
    path('analytes/<str:analyte_identifier>/history/', AnalyteHistoryAPIView.as_view(), name='analyte-history-api'),


    # Эндпоинт для получения списка загрузок пользователя
    # /api/submissions/
    path('submissions/', UserSubmissionsListAPIView.as_view(), name='submission-list-api'),

]
