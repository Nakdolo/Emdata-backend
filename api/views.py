# ==============================================================================
# Файл: api/views.py
# Описание: Представления (Views/Viewsets) DRF для API.
# ==============================================================================
import logging
from rest_framework import generics, permissions, viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView # <-- Импортируем APIView
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.http import Http404
from uuid import UUID
from django.utils.translation import gettext_lazy as _

# Импортируем модели
from data.models import TestResult, Analyte, MedicalTestSubmission
from users.models import User
from allauth.account.models import EmailConfirmationHMAC # <-- Для проверки ключа

# Импортируем сериализаторы
from .serializers import (
    AnalyteHistoryResultSerializer, SimpleAnalyteSerializer,
    MedicalTestSubmissionListSerializer, UserSerializer,
    VerifyEmailSerializer # <-- Наш сериализатор для верификации
)
# Импортируем адаптер для активации
from allauth.account.adapter import get_adapter

logger = logging.getLogger(__name__) # Используем логгер 'api'

# --- Кастомное Представление для Верификации Email (НОВОЕ) ---
class CustomVerifyEmailAPIView(APIView):
    """
    Обрабатывает POST-запрос с ключом для подтверждения email.
    Использует VerifyEmailSerializer и логику allauth/адаптера.
    """
    permission_classes = [permissions.AllowAny] # Доступно всем
    serializer_class = VerifyEmailSerializer # Используем наш сериализатор

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        # raise_exception=True вызовет ошибку 400, если ключ невалиден (согласно validate_key)
        serializer.is_valid(raise_exception=True)
        # Если валидация прошла, значит ключ валиден и объект confirmation сохранен в сериализаторе
        confirmation = serializer.confirmation

        try:
            # Выполняем подтверждение (помечает email как verified)
            confirmation.confirm(self.request)
            logger.info(f"Email confirmed successfully via API for key: {serializer.validated_data['key'][:10]}...")

            # --- Активируем пользователя через адаптер ---
            # Вызываем метод confirm_email нашего адаптера, который активирует пользователя
            adapter = get_adapter(self.request)
            adapter.confirm_email(self.request, confirmation.email_address)
            logger.info(f"User activation triggered via adapter for {confirmation.email_address.email}")
            # -------------------------------------------

            return Response({'detail': _('Email verified successfully.')}, status=status.HTTP_200_OK)

        # Перехватываем возможные (хотя и маловероятные после validate_key) ошибки
        except EmailConfirmationHMAC.DoesNotExist:
             logger.warning(f"Verify email API: Key does not exist (should have been caught by validate_key): {serializer.validated_data['key'][:10]}...")
             return Response({'detail': _('Invalid confirmation key.')}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
             logger.error(f"Error during email verification API for key {serializer.validated_data['key'][:10]}...: {e}", exc_info=True)
             return Response({'detail': _('An error occurred during verification.')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_serializer(self, *args, **kwargs):
        """Возвращает экземпляр сериализатора."""
        return self.serializer_class(*args, **kwargs)


# --- Представление для Списка Аналитов ---
class AnalyteListAPIView(generics.ListAPIView):
    queryset = Analyte.objects.all().order_by('name')
    serializer_class = SimpleAnalyteSerializer
    permission_classes = [permissions.IsAuthenticated]

# --- Представление для Истории Анализа ---
class AnalyteHistoryAPIView(generics.ListAPIView):
    serializer_class = AnalyteHistoryResultSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = { 'submission__test_date': ['gte', 'lte', 'exact', 'range'], }

    def get_analyte(self):
        identifier = self.kwargs.get('analyte_identifier')
        if not identifier: raise Http404("Analyte identifier not provided.")
        try:
            analyte_uuid = UUID(identifier)
            return Analyte.objects.get(id=analyte_uuid)
        except (ValueError, TypeError, Analyte.DoesNotExist):
            logger.debug(f"Identifier '{identifier}' not UUID or not found by UUID, searching by name/alias...")
            analyte = Analyte.objects.filter(
                Q(name__iexact=identifier) | Q(name_en__iexact=identifier) |
                Q(name_ru__iexact=identifier) | Q(name_kk__iexact=identifier) |
                Q(abbreviations__iexact=identifier)
            ).first()
            if not analyte:
                 possible_analytes = Analyte.objects.filter(abbreviations__icontains=identifier)
                 found_analytes = [pa for pa in possible_analytes if identifier.lower() in [a.strip().lower() for a in pa.abbreviations.split(',') if a.strip()]]
                 if len(found_analytes) == 1: analyte = found_analytes[0]
                 elif len(found_analytes) > 1: raise Http404(f"Ambiguous analyte identifier '{identifier}'.")
            if not analyte: raise Http404(f"Analyte '{identifier}' not found.")
            return analyte

    def get_queryset(self):
        user = self.request.user
        analyte = self.get_analyte()
        logger.info(f"Fetching history for analyte '{analyte.name}' (ID: {analyte.id}) for user {user.id}")
        return TestResult.objects.filter(
            submission__user=user, analyte=analyte, value_numeric__isnull=False,
            submission__test_date__isnull=False
        ).select_related('submission', 'analyte').order_by('submission__test_date')

# --- Представление для Списка Загрузок Пользователя ---
class UserSubmissionsListAPIView(generics.ListAPIView):
    serializer_class = MedicalTestSubmissionListSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'submission_date': ['gte', 'lte', 'exact', 'range'],
        'test_date': ['gte', 'lte', 'exact', 'range'],
        'processing_status': ['exact', 'in'], 'test_type': ['exact'],
    }
    def get_queryset(self):
        return MedicalTestSubmission.objects.filter(user=self.request.user).select_related('test_type').order_by('-submission_date')

# --- Представление для Получения Информации о Пользователе ---
class UserDetailAPIView(generics.RetrieveAPIView):
     serializer_class = UserSerializer
     permission_classes = [permissions.IsAuthenticated]
     def get_object(self): return self.request.user

