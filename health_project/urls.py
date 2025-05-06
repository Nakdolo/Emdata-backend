# ==============================================================================
# Файл: health_project/urls.py (Возврат к include)
# ==============================================================================

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

# Swagger / Redoc
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

# Custom views
from data.views import UploadMedicalTestView, SubmissionStatusView, DownloadSubmissionFileView
# Убираем импорт account_inactive, т.к. он будет в include('allauth.urls')
# from allauth.account.views import account_inactive

schema_view = get_schema_view(
   openapi.Info(
      title="Health Platform API",
      default_version='v1',
      description="API documentation",
      contact=openapi.Contact(email="contact@healthplatform.local"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # --- API ---
    # URL dj-rest-auth для входа, выхода, сброса пароля и т.д.
    path('api/auth/', include('dj_rest_auth.urls')),
    # --- ИСПОЛЬЗУЕМ СТАНДАРТНЫЙ INCLUDE ДЛЯ РЕГИСТРАЦИИ И ВЕРИФИКАЦИИ ---
    # Эта строка подключит /api/auth/registration/ (для POST)
    # и /api/auth/registration/verify-email/ (для POST)
    path('api/auth/registration/', include('dj_rest_auth.registration.urls')), # <-- ВОЗВРАЩАЕМ ЭТО
    # --------------------------------------------------------------------

    # --- Основное API (убедись, что в api.urls нет /auth/...) ---
    path('api/', include('api.urls')), # Подключаем URL из api/urls.py

    # --- Swagger/Redoc ---
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # --- Allauth URLs (включая account_inactive и стандартные страницы) ---
    path('accounts/', include('allauth.urls')),
    # ---------------------------------------------------------------------

    # --- Веб-интерфейс для загрузки данных ---
    path('upload/', UploadMedicalTestView.as_view(), name='upload_medical_test_url'),
    path('upload/success/', TemplateView.as_view(template_name="data/upload_success.html"), name='upload_success_page'),
    path('submission/<uuid:submission_id>/status/', SubmissionStatusView.as_view(), name='submission_status_url'),
    path('submission/<uuid:submission_id>/download/', DownloadSubmissionFileView.as_view(), name='submission_download_url'),
]

# --- Media files in DEBUG ---
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

