# ==============================================================================
# Файл: data/urls.py
# Описание: URL-маршруты для приложения data (не API).
# Включает URL для скачивания загруженных файлов.
# ==============================================================================
from django.urls import path
from .views import (
    # UploadMedicalTestView, # <-- Старый View для форм, можно закомментировать/удалить если не нужен
    SubmissionStatusView, # View для страницы статуса (если используется)
    DownloadSubmissionFileView, # <-- View для скачивания файла
)

# App name для использования в reverse('data:...') в Django шаблонах
# и для построения URL на фронтенде, если вы используете reverse в Django для генерации URL
app_name = 'data'

urlpatterns = [
    # Старый URL для загрузки через обычную форму (можно удалить, если используешь только API)
    # path('upload/form/', UploadMedicalTestView.as_view(), name='upload_form_view'),

    # URL для страницы статуса (на нее можно перенаправлять после старой формы или просто показывать)
    # Если вы используете эту страницу, оставьте URL.
    path('submissions/<uuid:submission_id>/status/', SubmissionStatusView.as_view(), name='submission_status_url'),

    # --- URL для скачивания загруженного файла ---
    # Этот URL используется фронтендом для создания ссылки на скачивание
    # <uuid:submission_id> соответствует полю id в модели MedicalTestSubmission
    path('submissions/<uuid:submission_id>/download/', DownloadSubmissionFileView.as_view(), name='download_submission_file_url'),
    # ---------------------------------------------

    # Добавь здесь другие URLы, если они есть в приложении data (не API)

]
