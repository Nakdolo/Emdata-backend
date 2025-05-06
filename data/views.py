# ==============================================================================
# Файл: data/views.py
# Описание: Представления Django для приложения data.
# ==============================================================================

import logging
import threading
import os # Для работы с путями файлов
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.urls import reverse
from django.http import HttpResponseForbidden, HttpResponseRedirect, Http404, FileResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib import messages # Для сообщений пользователю

# Импортируем модели и задачу из текущего приложения
from .models import MedicalTestSubmission
from .tasks import process_pdf_submission_plain

# Логгер для представлений
view_logger = logging.getLogger('data.views')

# --- Форма Загрузки ---
class MedicalTestSubmissionForm(forms.ModelForm):
    class Meta:
        model = MedicalTestSubmission
        fields = ['test_type', 'test_date', 'notes', 'uploaded_file']
        widgets = {
            'test_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
        labels = {
            'test_type': _('Test Type (optional)'),
            'test_date': _('Date of Test (optional)'),
            'notes': _('Notes (optional)'),
            'uploaded_file': _('PDF File *'),
        }
        help_texts = {
            'test_date': _('Date the test was performed.'),
            'uploaded_file': _('Only PDF files are allowed.'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['test_type'].required = False
        self.fields['test_date'].required = False
        self.fields['notes'].required = False
        self.fields['uploaded_file'].required = True

    def clean_uploaded_file(self):
        file = self.cleaned_data.get('uploaded_file', None)
        if file:
            if not file.name.lower().endswith('.pdf'):
                raise forms.ValidationError(_("Only PDF files are allowed."))
        elif not file:
             raise forms.ValidationError(_("This field is required."))
        return file

# --- Представление для Загрузки Файла ---
class UploadMedicalTestView(LoginRequiredMixin, View):
    form_class = MedicalTestSubmissionForm
    template_name = 'data/upload_form.html'

    def get(self, request, *args, **kwargs):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.user = request.user
            submission.processing_status = MedicalTestSubmission.StatusChoices.PENDING
            try:
                 submission.save()
                 view_logger.info(f"User {request.user.id} submitted file for submission {submission.id}. Scheduling background processing.")
            except Exception as e:
                 view_logger.error(f"Error saving submission for user {request.user.id}: {e}", exc_info=True)
                 form.add_error(None, _("An error occurred while saving the submission. Please try again."))
                 return render(request, self.template_name, {'form': form})

            try:
                thread = threading.Thread(
                    target=process_pdf_submission_plain,
                    args=(submission.id,),
                    daemon=True
                )
                thread.start()
                view_logger.info(f"Started background thread {thread.ident} for submission {submission.id}")
            except Exception as thread_err:
                 view_logger.exception(f"Failed to start background thread for submission {submission.id}: {thread_err}", exc_info=True)
                 submission.processing_status = MedicalTestSubmission.StatusChoices.FAILED
                 submission.processing_details = f"Failed to start processing thread: {str(thread_err)}"
                 submission.save(update_fields=['processing_status', 'processing_details'])
                 messages.error(request, _("The file was saved, but an error occurred starting the background processing. Please contact support."))
                 status_url = reverse('submission_status_url', kwargs={'submission_id': submission.id})
                 return HttpResponseRedirect(status_url)

            # Перенаправляем на страницу статуса
            status_url = reverse('submission_status_url', kwargs={'submission_id': submission.id})
            return HttpResponseRedirect(status_url)
        else:
            view_logger.warning(f"User {request.user.id} submitted invalid form: {form.errors.as_json()}")
            return render(request, self.template_name, {'form': form})

# --- Представление для Отображения Статуса ---
class SubmissionStatusView(LoginRequiredMixin, View):
    template_name = 'data/submission_status.html'

    def get(self, request, submission_id, *args, **kwargs):
        submission = get_object_or_404(MedicalTestSubmission, id=submission_id, user=request.user)
        context = {'submission': submission}
        return render(request, self.template_name, context)

# --- Представление для Скачивания Файла (НОВОЕ) ---
class DownloadSubmissionFileView(LoginRequiredMixin, View):
    """
    Позволяет пользователю скачать PDF-файл, который он загрузил.
    """
    def get(self, request, submission_id, *args, **kwargs):
        # Находим загрузку, принадлежащую текущему пользователю
        submission = get_object_or_404(MedicalTestSubmission, id=submission_id, user=request.user)

        # Проверяем, есть ли файл
        if not submission.uploaded_file:
            view_logger.warning(f"User {request.user.id} tried to download file for submission {submission.id}, but file is missing.")
            raise Http404("File not found for this submission.")

        try:
            # Получаем путь к файлу
            file_path = submission.uploaded_file.path
            view_logger.info(f"User {request.user.id} downloading file: {file_path}")

            # Используем FileResponse для эффективной отдачи файла
            response = FileResponse(open(file_path, 'rb'), as_attachment=True, filename=os.path.basename(file_path))
            # as_attachment=True говорит браузеру скачать файл
            # filename=... устанавливает имя файла для скачивания
            return response

        except FileNotFoundError:
            view_logger.error(f"File not found on disk for submission {submission.id} at path: {submission.uploaded_file.path}")
            raise Http404("File not found on server.")
        except Exception as e:
            view_logger.error(f"Error serving file for submission {submission.id}: {e}", exc_info=True)
            # Можно вернуть страницу с ошибкой или сообщение
            messages.error(request, _("An error occurred while trying to download the file."))
            # Перенаправляем обратно на страницу статуса
            status_url = reverse('submission_status_url', kwargs={'submission_id': submission.id})
            return HttpResponseRedirect(status_url)

