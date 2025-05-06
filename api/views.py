# ==============================================================================
# Файл: api/views.py
# Описание: Представления (Views/Viewsets) DRF для API.
# ==============================================================================
import logging
from rest_framework import generics, permissions, viewsets, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend

# Импортируем модели
from data.models import TestResult, Analyte, MedicalTestSubmission
from users.models import User

# Импортируем сериализаторы
from .serializers import (
    AnalyteHistoryResultSerializer, SimpleAnalyteSerializer,
    MedicalTestSubmissionListSerializer, UserSerializer
)

logger = logging.getLogger(__name__)

# --- Представление для Истории Анализа ---
class AnalyteHistoryAPIView(generics.ListAPIView):
    """
    Возвращает историю результатов для конкретного анализа
    текущего аутентифицированного пользователя.
    """
    serializer_class = AnalyteHistoryResultSerializer
    permission_classes = [permissions.IsAuthenticated] # Доступ только для вошедших пользователей
    filter_backends = [DjangoFilterBackend] # Включаем фильтрацию
    filterset_fields = { # Определяем поля для фильтрации по дате
        'submission__test_date': ['gte', 'lte', 'exact', 'range'], # >=, <=, ==, между датами
    }

    def get_queryset(self):
        user = self.request.user
        # Получаем ID или имя анализа из URL (см. api/urls.py)
        analyte_identifier = self.kwargs.get('analyte_identifier')

        if not analyte_identifier:
            # Если идентификатор не передан, можно вернуть пустой queryset или ошибку
            logger.warning(f"Analyte identifier not provided for history request by user {user.id}")
            return TestResult.objects.none()

        # Пытаемся найти анализ по UUID или по имени/алиасу
        try:
            # Сначала пробуем как UUID
            from uuid import UUID
            analyte_uuid = UUID(analyte_identifier)
            analyte = get_object_or_404(Analyte, id=analyte_uuid)
        except (ValueError, TypeError):
            # Если не UUID, ищем по имени/алиасу (регистронезависимо)
            # Это менее надежно, если есть похожие названия
            analyte = Analyte.objects.filter(
                models.Q(name__iexact=analyte_identifier) |
                models.Q(name_en__iexact=analyte_identifier) |
                models.Q(name_ru__iexact=analyte_identifier) |
                models.Q(name_kk__iexact=analyte_identifier) |
                models.Q(abbreviations__icontains=analyte_identifier) # Поиск по аббревиатурам (может дать неточные результаты)
            ).first()
            if not analyte:
                 logger.warning(f"Analyte '{analyte_identifier}' not found for history request by user {user.id}")
                 raise Http404("Analyte not found.") # Возвращаем 404, если анализ не найден

        logger.info(f"Fetching history for analyte '{analyte.name}' (ID: {analyte.id}) for user {user.id}")

        # Фильтруем результаты:
        # - Принадлежат текущему пользователю
        # - Относятся к найденному аналиту
        # - Имеют числовое значение (для графиков)
        # - Имеют дату теста (для сортировки и графиков)
        # - Сортируем по дате теста
        queryset = TestResult.objects.filter(
            submission__user=user,
            analyte=analyte,
            value_numeric__isnull=False, # Только те, где есть числовое значение
            submission__test_date__isnull=False # Только те, где есть дата теста
        ).select_related('submission', 'analyte').order_by('submission__test_date') # Сортируем по дате

        return queryset

# --- Представление для Списка Аналитов ---
class AnalyteListAPIView(generics.ListAPIView):
    """
    Возвращает список всех доступных аналитов (ID, имя, единица).
    """
    queryset = Analyte.objects.all().order_by('name')
    serializer_class = SimpleAnalyteSerializer
    permission_classes = [permissions.IsAuthenticated] # Доступно только вошедшим
    # Можно добавить поиск/фильтрацию, если нужно
    # filter_backends = [filters.SearchFilter]
    # search_fields = ['name', 'name_en', 'name_ru', 'name_kk', 'abbreviations']

# --- Представление для Списка Загрузок Пользователя ---
class UserSubmissionsListAPIView(generics.ListAPIView):
    """
    Возвращает список загрузок текущего пользователя.
    """
    serializer_class = MedicalTestSubmissionListSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'submission_date': ['gte', 'lte', 'exact', 'range'],
        'test_date': ['gte', 'lte', 'exact', 'range'],
        'processing_status': ['exact', 'in'],
        'test_type': ['exact'],
    }

    def get_queryset(self):
        # Возвращаем только загрузки текущего пользователя
        return MedicalTestSubmission.objects.filter(user=self.request.user).select_related('test_type').order_by('-submission_date')


# --- Представление для Получения Информации о Пользователе ---
class UserDetailAPIView(generics.RetrieveAPIView):
     """
     Возвращает информацию о текущем пользователе.
     """
     serializer_class = UserSerializer
     permission_classes = [permissions.IsAuthenticated]

     def get_object(self):
         # Возвращаем текущего пользователя
         return self.request.user


# --- ViewSet для загрузки (если нужен API для загрузки) ---
# class MedicalTestSubmissionAPIViewSet(viewsets.ModelViewSet):
#     serializer_class = MedicalTestSubmissionSerializer # Нужен другой сериализатор для создания
#     permission_classes = [permissions.IsAuthenticated]
#     parser_classes = [MultiPartParser, FormParser] # Для загрузки файлов

#     def get_queryset(self):
#         return MedicalTestSubmission.objects.filter(user=self.request.user)

#     def perform_create(self, serializer):
#         submission = serializer.save(user=self.request.user)
#         if submission.uploaded_file and submission.uploaded_file.name.lower().endswith('.pdf'):
#             # Запускаем задачу парсинга (возможно, через Celery в продакшене)
#             from data.tasks import process_pdf_submission_plain
#             import threading
#             thread = threading.Thread(target=process_pdf_submission_plain, args=(submission.id,), daemon=True)
#             thread.start()
#             logger.info(f"API: Started background thread for submission {submission.id}")
#         else:
#              logger.warning(f"API: Submission {submission.id} created without a valid PDF file.")
#              # Можно сразу пометить как FAILED
#              submission.processing_status = MedicalTestSubmission.StatusChoices.FAILED
#              submission.processing_details = "No valid PDF file provided during API upload."
#              submission.save()

