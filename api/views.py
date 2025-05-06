# ==============================================================================
# Файл: api/views.py
# Описание: Представления (Views/Viewsets) DRF для API.
# Включает представления для загрузки файлов и списка загрузок.
# ==============================================================================
import logging
import threading # Для запуска задачи парсинга в отдельном потоке (для простой демонстрации)
import os # Для работы с путями файлов
import datetime
from urllib.parse import unquote # Для обработки даты
from rest_framework import generics, permissions, viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser # Для обработки файлов в POST запросах
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.http import Http404
from uuid import UUID
from django.utils.translation import gettext_lazy as _
from django.utils import timezone # Для работы с временными зонами
from django.conf import settings # Для доступа к настройкам проекта (например, MAX_UPLOAD_SIZE)
from django.db import transaction # Для атомарных операций с базой данных

# --- Добавлен недостающий импорт ---
from rest_framework import serializers
# ------------------------------------

# Импортируем модели из приложения data
from data.models import TestResult, Analyte, MedicalTestSubmission, TestType
# Импортируем модель пользователя (предполагается, что это settings.AUTH_USER_MODEL)
from users.models import User # Убедитесь, что это правильный импорт для вашего проекта
# Импортируем EmailConfirmationHMAC для верификации email (часть allauth)
from allauth.account.models import EmailConfirmationHMAC
# Импортируем адаптер allauth для активации пользователя
from allauth.account.adapter import get_adapter

# Импортируем задачу парсинга PDF из приложения data
from data.tasks import process_pdf_submission_plain # Убедитесь, что путь правильный

# Импортируем сериализаторы из текущего приложения api
from .serializers import (
    AnalyteHistoryResultSerializer,
    MedicalTestSubmissionDetailSerializer,
    SimpleAnalyteSerializer,
    MedicalTestSubmissionListSerializer,
    UserSerializer,
    VerifyEmailSerializer,
    # Если у вас есть отдельный сериализатор для загрузки, импортируйте его здесь
    # MedicalTestSubmissionUploadSerializer
)

# Инициализируем логгер для представлений API
logger = logging.getLogger(__name__)

# --- Кастомное Представление для Верификации Email ---
# Этот код оставлен без изменений, так как он не относится напрямую к загрузке/списку
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
# Этот код оставлен без изменений
class AnalyteListAPIView(generics.ListAPIView):
    queryset = Analyte.objects.all().order_by('name')
    serializer_class = SimpleAnalyteSerializer
    permission_classes = [permissions.IsAuthenticated]

# --- Представление для Истории Анализа ---
# Этот код оставлен без изменений
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
# Этот код оставлен без изменений, он предоставляет данные для фронтенда
class UserSubmissionsListAPIView(generics.ListAPIView):
    """
    Предоставляет список загрузок медицинских тестов для текущего пользователя.
    """
    serializer_class = MedicalTestSubmissionListSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'submission_date': ['gte', 'lte', 'exact', 'range'],
        'test_date': ['gte', 'lte', 'exact', 'range'],
        'processing_status': ['exact', 'in'],
        'test_type': ['exact'], # Фильтрация по UUID TestType
    }

    def get_queryset(self):
        # Возвращаем только загрузки текущего пользователя
        return MedicalTestSubmission.objects.filter(user=self.request.user).select_related('test_type').order_by('-submission_date')


# --- Представление для Получения Информации о Пользователе ---
# Этот код оставлен без изменений
class UserDetailAPIView(generics.RetrieveAPIView):
     serializer_class = UserSerializer
     permission_classes = [permissions.IsAuthenticated]
     def get_object(self): return self.request.user


# --- НОВОЕ Представление для Загрузки Лабораторных Результатов ---
# Этот код обрабатывает POST запросы от фронтенда с файлами
class UploadLabResultsAPIView(APIView):
    """
    Принимает файл(ы) лабораторных тестов через API, создает запись MedicalTestSubmission
    и запускает фоновую задачу для парсинга.
    """
    permission_classes = [permissions.IsAuthenticated] # Требуем аутентификацию
    parser_classes = [MultiPartParser, FormParser] # Разрешаем прием файлов и форм-данных (FormData)

    def post(self, request, *args, **kwargs):
        user = request.user # Текущий аутентифицированный пользователь
        files = request.FILES.getlist('files') # Получаем список файлов по имени 'files' из FormData

        # Проверяем, были ли файлы загружены
        if not files:
            logger.warning(f"User {user.id} attempted upload with no files.")
            return Response({'detail': _('No files uploaded.')}, status=status.HTTP_400_BAD_REQUEST)

        # Валидация типов файлов и размера
        allowed_extensions = ['.pdf']
        for file in files:
            name, ext = os.path.splitext(file.name)
            if ext.lower() not in allowed_extensions:
                logger.warning(f"User {user.id} attempted upload with disallowed file type: {file.name}")
                return Response({'detail': _("Only PDF files are allowed.")}, status=status.HTTP_400_BAD_REQUEST)
            # Проверяем размер файла, если MAX_UPLOAD_SIZE определен в settings.py
            if hasattr(settings, 'MAX_UPLOAD_SIZE') and file.size > settings.MAX_UPLOAD_SIZE:
                 logger.warning(f"User {user.id} attempted upload exceeding size limit: {file.name}")
                 return Response({'detail': _(f'File size exceeds the limit: {file.name}')}, status=status.HTTP_400_BAD_REQUEST)

        # Получаем дополнительные данные из request.data (POST-параметры формы)
        # Фронтенд может отправлять эти поля, но они необязательны
        test_type_id = request.data.get('test_type')
        test_date_str = request.data.get('test_date') # Ожидаем формат-MM-DD
        notes = request.data.get('notes')

        test_type = None
        if test_type_id:
            try:
                # Ищем TestType по ID (ожидаем UUID)
                test_type = TestType.objects.get(id=test_type_id)
                logger.debug(f"Found TestType by ID: {test_type.name}")
            except (ValueError, TestType.DoesNotExist):
                 # Обрабатываем ошибку, если тип теста указан, но невалиден
                 logger.warning(f"User {user.id} uploaded file with invalid test_type_id: {test_type_id}")
                 # Возвращаем ошибку, чтобы фронтенд знал о проблеме
                 return Response({'detail': _('Invalid test type specified.')}, status=status.HTTP_400_BAD_REQUEST)

        test_date = None
        if test_date_str:
            try:
                 # Парсим дату из строки (предполагаем формат 'YYYY-MM-DD')
                test_date = datetime.date.fromisoformat(test_date_str)
                logger.debug(f"Parsed test date: {test_date}")
            except ValueError:
                 logger.warning(f"User {user.id} uploaded file with invalid test_date format: {test_date_str}")
                 # Возвращаем ошибку
                 return Response({'detail': _('Invalid date format for test date. Use-MM-DD.')}, status=status.HTTP_400_BAD_REQUEST)

        submission_ids = []
        try:
            # Используем транзакцию на случай загрузки нескольких файлов
            # Это гарантирует, что если один файл вызовет ошибку сохранения,
            # все предыдущие сохранения в этой транзакции будут отменены.
            with transaction.atomic():
                for file in files:
                    # Создаем запись MedicalTestSubmission в базе данных
                    submission = MedicalTestSubmission.objects.create(
                        user=user, # Привязываем загрузку к текущему пользователю
                        test_type=test_type, # Может быть None, если не указан
                        test_date=test_date, # Может быть None, если не указана
                        notes=notes, # Может быть None, если не указаны
                        uploaded_file=file, # Файл автоматически сохраняется в MEDIA_ROOT
                        processing_status=MedicalTestSubmission.StatusChoices.PENDING, # Начальный статус
                        submission_date=timezone.now(), # Дата и время загрузки
                        created_at=timezone.now(),
                        updated_at=timezone.now(),
                    )
                    # Добавляем ID созданной загрузки в список для ответа
                    submission_ids.append(str(submission.id))
                    logger.info(f"User {user.id} uploaded file {file.name}. Created submission {submission.id}. Scheduling background processing.")

                    # --- Запуск фоновой задачи парсинга ---
                    # В ПРОДАКШЕНЕ: Используй Celery или другую надежную очередь задач!
                    # threading.Thread - это простой способ для локальной разработки/демонстрации.
                    # Он не надежен в продакшене (задачи могут потеряться при падении сервера).
                    try:
                        thread = threading.Thread(
                            target=process_pdf_submission_plain, # Ваша функция парсинга
                            args=(submission.id,), # Передаем ID созданной загрузки
                            daemon=True # Поток завершится, когда завершится основная программа
                        )
                        thread.start()
                        logger.info(f"Started background thread {thread.ident} for submission {submission.id}")
                    except Exception as thread_start_err:
                         # Если не удалось запустить поток, помечаем загрузку как FAILED
                         logger.exception(f"Failed to start background thread for submission {submission.id}: {thread_start_err}", exc_info=True)
                         submission.processing_status = MedicalTestSubmission.StatusChoices.FAILED
                         submission.processing_details = f"Failed to start processing thread: {str(thread_start_err)}"
                         submission.save(update_fields=['processing_status', 'processing_details', 'updated_at'])
                         # Можно также вернуть ошибку фронтенду сразу, или позволить ему отслеживать статус
                         # В данном случае, просто логируем и помечаем как FAILED на бэкенде.
                         # Фронтенд увидит статус FAILED при следующем обновлении списка.


            # Возвращаем успешный ответ со списком ID созданных загрузок
            # Фронтенд может использовать эти ID для отслеживания статуса
            return Response({
                'detail': _('Files uploaded and processing started.'),
                'submission_ids': submission_ids # Список ID всех созданных загрузок
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            # Ловим любые другие ошибки при сохранении в БД или запуске потока (если не пойманы выше)
            logger.exception(f"Error during file upload or task scheduling for user {user.id}: {e}", exc_info=True)
            # Возвращаем общую ошибку фронтенду
            return Response({'detail': _('An error occurred during the upload process.')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# --- Сериализатор для Подтверждения Email ---
# Этот код оставлен без изменений
class VerifyEmailSerializer(serializers.Serializer):
     key = serializers.CharField(write_only=True)

     def validate_key(self, key):
         try:
             decoded_key = unquote(key)
             self.confirmation = EmailConfirmationHMAC.from_key(decoded_key)
             if not self.confirmation:
                  raise serializers.ValidationError(_('Invalid confirmation key.'))
         except Exception: # Ловим любые ошибки при разборе ключа
              raise serializers.ValidationError(_('Invalid confirmation key.'))
         return key

     def save(self):
         # Логика подтверждения будет в представлении (view)
         pass


class SubmissionDetailAPIView(generics.RetrieveAPIView):
    """
    Предоставляет детали одной загрузки медицинского теста по ID, включая связанные результаты.
    """
    queryset = MedicalTestSubmission.objects.select_related('test_type', 'user').prefetch_related('results__analyte').all()
    serializer_class = MedicalTestSubmissionDetailSerializer # Используем новый сериализатор
    permission_classes = [permissions.IsAuthenticated] # Требуем аутентификацию
    lookup_field = 'id' # Поле в URL для поиска объекта (по умолчанию 'pk')

    def get_queryset(self):
        # Убеждаемся, что пользователь может просматривать только свои загрузки
        return self.queryset.filter(user=self.request.user)

    # Нет необходимости переопределять retrieve, т.к. generics.RetrieveAPIView делает это автоматически
