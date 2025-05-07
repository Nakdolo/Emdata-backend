# ==============================================================================
# Файл: data/views.py
# Описание: Представления Django для приложения data.
# ==============================================================================

import logging
import threading # Not used in DownloadSubmissionFileView or DeleteSubmissionView
import os
from django.shortcuts import get_object_or_404 # render, redirect not used by these API views
from django.views import View # Not used by these API views
from django.urls import reverse # Not used by these API views
from django.http import Http404, FileResponse # HttpResponseForbidden, HttpResponseRedirect, JsonResponse not used by these API views
from django.contrib.auth.mixins import LoginRequiredMixin # Not used by these API views
from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib import messages # Not used by these API views

# CORRECTED IMPORT: Changed from 'requests' to 'rest_framework.response'
from rest_framework.response import Response
from rest_framework import authentication, permissions
from rest_framework.views import APIView
from rest_framework import status

from .models import MedicalTestSubmission

view_logger = logging.getLogger('data.views')

# --- Форма Загрузки (Оставлена как есть из вашего файла) ---
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
        elif not file: # This condition might be redundant if uploaded_file.required = True
             raise forms.ValidationError(_("This field is required."))
        return file

# --- Представление для Скачивания Файла ---
class DownloadSubmissionFileView(APIView):
    authentication_classes = [authentication.TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, submission_id, *args, **kwargs):
        submission = get_object_or_404(MedicalTestSubmission, id=submission_id, user=request.user)

        if not submission.uploaded_file:
            # Using DRF Response for consistency in API views
            return Response({"detail": "File not found for this submission."}, status=status.HTTP_404_NOT_FOUND)

        try:
            file_path = submission.uploaded_file.path
            # FileResponse is a Django HTTP response, suitable for sending files.
            response = FileResponse(open(file_path, 'rb'), as_attachment=True, filename=os.path.basename(file_path))
            return response
        except FileNotFoundError:
            view_logger.warning(f"File not found on server for submission {submission_id} at path {submission.uploaded_file.path if submission.uploaded_file else 'N/A'}")
            return Response({"detail": "File not found on server."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            view_logger.error(f"Error downloading file for submission {submission_id}: {e}", exc_info=True)
            # Using DRF Response
            return Response({"detail": "An error occurred while trying to download the file."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# --- Представление для Удаления Загрузки ---
class DeleteSubmissionView(APIView):
    authentication_classes = [authentication.TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, submission_id, *args, **kwargs):
        """
        Allows a user to delete their submission and the associated file.
        This view is intended to be called if specifically routed, e.g. /api/submissions/<id>/delete/
        """
        submission = get_object_or_404(MedicalTestSubmission, id=submission_id, user=request.user)

        file_path = None
        if submission.uploaded_file and hasattr(submission.uploaded_file, 'path'):
            file_path = submission.uploaded_file.path

        try:
            submission.delete() # This also triggers the post_delete signal in models.py if defined
            view_logger.info(
                f"User {request.user.id} deleted submission {submission_id} record."
            )

            # File deletion from disk should ideally be handled by a post_delete signal 
            # on the MedicalTestSubmission model. If you have such a signal, this manual
            # os.remove is not needed here and might even cause issues if the file is already gone.
            # If you DON'T have a post_delete signal for file cleanup:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    view_logger.info(f"File deleted from disk: {file_path}")
                except OSError as e:
                    view_logger.error(f"Error deleting file {file_path} from disk: {e}", exc_info=True)
            elif submission.uploaded_file and not (file_path and os.path.exists(file_path)):
                 view_logger.warning(
                     f"File path {file_path if file_path else 'not available'} was recorded for submission {submission_id}, but file not found on disk or path was invalid during deletion attempt."
                 )

            # Option 1: Standard DRF practice for DELETE is to return 204 No Content
            # return Response(status=status.HTTP_204_NO_CONTENT)
            
            # Option 2: If frontend strictly needs a body (as per your original frontend code)
            return Response({'status': 'success', 'message': 'Submission deleted successfully.'}, status=status.HTTP_200_OK)

        except Exception as e:
            view_logger.error(
                f"Error during submission record deletion or file handling for {submission_id}, user {request.user.id}: {e}",
                exc_info=True,
            )
            # Using DRF Response
            return Response(
                {'detail': _("An error occurred while trying to delete the submission.")},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
