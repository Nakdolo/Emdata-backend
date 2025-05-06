# ==============================================================================
# Файл: api/serializers.py
# Описание: Сериализаторы DRF для API.
# ==============================================================================
import logging
from rest_framework import serializers
# Импортируем ТОЛЬКО базовый RegisterSerializer
from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import PasswordResetSerializer as BasePasswordResetSerializer
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
# Убираем ненужные импорты allauth utils и transaction
from allauth.account.models import EmailAddress # Оставляем для валидации
# from allauth.account import app_settings as allauth_app_settings
# from allauth.account.adapter import get_adapter
# from django.db import transaction
# from django.conf import settings
# from django.utils import translation

# Импортируем нашу кастомную форму
from .forms import CustomResetPasswordForm

# Импортируем остальные нужные модели и сериализаторы
from data.models import TestResult, Analyte, MedicalTestSubmission, TestType
from users.models import UserProfile

User = get_user_model()
logger = logging.getLogger(__name__)

# --- Кастомный Сериализатор Регистрации (Максимально упрощенный) ---
class CustomRegisterSerializer(RegisterSerializer):
    """
    Переопределяем стандартный RegisterSerializer ТОЛЬКО для добавления поля username.
    Вся остальная логика (валидация email, паролей, сохранение, отправка письма) наследуется.
    Стандартная логика должна использовать ACCOUNT_EMAIL_CONFIRMATION_URL из settings.
    """
    # Добавляем поле username, которое обязательно
    username = serializers.CharField(required=True, max_length=150)

    # Поля email, password, password2 наследуются и обрабатываются родительским классом

    def validate_username(self, username):
        # Проверка на существование пользователя с таким username
        if User.objects.filter(username__iexact=username).exists():
             raise serializers.ValidationError(_("A user with that username already exists."))
        # Можно добавить другие валидации username
        return username

    # Валидация email будет выполнена стандартным сериализатором с учетом unique=True в модели
    # и проверкой allauth, если она настроена

    # Валидация совпадения паролей выполняется стандартным сериализатором

    # НЕ переопределяем save - стандартный save вызовет create_user менеджера и отправит письмо,
    # используя настройки allauth (включая ACCOUNT_EMAIL_CONFIRMATION_URL)


# --- Кастомный Сериализатор для Запроса Сброса Пароля ---
class CustomPasswordResetSerializer(BasePasswordResetSerializer):
    @property
    def password_reset_form_class(self):
        return CustomResetPasswordForm


# --- Сериализатор для Подтверждения Email ---
class VerifyEmailSerializer(serializers.Serializer):
    key = serializers.CharField(write_only=True)

    def validate_key(self, key):
        try:
            # Используем EmailConfirmationHMAC для поиска ключа
            from allauth.account.models import EmailConfirmationHMAC
            self.confirmation = EmailConfirmationHMAC.from_key(key)
            if not self.confirmation:
                 # Если ключ не найден или невалиден по формату HMAC
                 logger.warning(f"VerifyEmailSerializer: Invalid or non-existent key format: {key[:10]}...")
                 raise serializers.ValidationError(_('Invalid confirmation key.'))
            # Дополнительная проверка: не истек ли срок действия ключа?
            if self.confirmation.key_expired():
                 logger.warning(f"VerifyEmailSerializer: Expired key used: {key[:10]}...")
                 raise serializers.ValidationError(_('Confirmation key expired.'))
        except Exception as e: # Ловим любые другие ошибки при разборе ключа
             logger.error(f"VerifyEmailSerializer: Error validating key {key[:10]}...: {e}", exc_info=True)
             raise serializers.ValidationError(_('Invalid confirmation key.'))
        return key

    def save(self):
        # Логика подтверждения будет в представлении (view)
        pass


# --- Остальные сериализаторы (без изменений) ---
class AnalyteHistoryResultSerializer(serializers.ModelSerializer):
    test_date = serializers.DateField(source='submission.test_date', read_only=True)
    analyte_name = serializers.CharField(source='analyte.name', read_only=True)
    unit = serializers.CharField(read_only=True)
    class Meta: model = TestResult; fields = ['id', 'analyte_name', 'test_date', 'value_numeric','unit', 'is_abnormal', 'status_text', 'reference_range', 'submission']; read_only_fields = fields

class SimpleAnalyteSerializer(serializers.ModelSerializer):
    class Meta: model = Analyte; fields = ['id', 'name', 'unit']; read_only_fields = fields

class MedicalTestSubmissionListSerializer(serializers.ModelSerializer):
    test_type_name = serializers.CharField(source='test_type.name', read_only=True, allow_null=True)
    file_name = serializers.SerializerMethodField()
    class Meta: model = MedicalTestSubmission; fields = ['id', 'submission_date', 'test_date', 'test_type_name', 'processing_status', 'file_name']; read_only_fields = fields
    def get_file_name(self, obj):
        if obj.uploaded_file: import os; return os.path.basename(obj.uploaded_file.name)
        return None

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta: model = UserProfile; fields = ['date_of_birth', 'phone_number', 'bio', 'profile_picture']

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    class Meta: model = User; fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile']

