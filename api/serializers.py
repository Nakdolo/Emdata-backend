# ==============================================================================
# Файл: api/serializers.py
# Описание: Сериализаторы DRF для API.
# ==============================================================================
import logging
from rest_framework import serializers
from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import PasswordResetSerializer as BasePasswordResetSerializer
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from allauth.account.models import EmailAddress, EmailConfirmationHMAC
from allauth.account import app_settings as allauth_app_settings
from allauth.account.adapter import get_adapter
from django.db import transaction
from django.conf import settings
# Импортируем функцию для получения языка из запроса
from django.utils import translation
from urllib.parse import unquote

# Импортируем нашу кастомную форму
from .forms import CustomResetPasswordForm

# Импортируем остальные нужные модели и сериализаторы
from data.models import TestResult, Analyte, MedicalTestSubmission, TestType
from users.models import UserProfile

User = get_user_model()
logger = logging.getLogger(__name__)

# --- Кастомный Сериализатор Регистрации (Добавление locale в URL верификации) ---
class CustomRegisterSerializer(RegisterSerializer):
    username = serializers.CharField(required=True, max_length=150)
    email = serializers.EmailField(required=True)
    password1 = serializers.CharField(write_only=True, style={'input_type': 'password'}, label=_("Password"))
    password2 = serializers.CharField(write_only=True, style={'input_type': 'password'}, label=_("Confirm Password"))

    def validate_username(self, username):
        if User.objects.filter(username__iexact=username).exists():
             raise serializers.ValidationError(_("A user with that username already exists."))
        return username

    def validate_email(self, email):
        if EmailAddress.objects.filter(email__iexact=email).exists():
             raise serializers.ValidationError(_("A user is already registered with this e-mail address."))
        return email

    def validate(self, data):
        password = data.get('password1')
        password2 = data.get('password2')
        if password != password2:
            raise serializers.ValidationError({'password2': _('The two password fields didn’t match.')})
        try:
            from django.contrib.auth.password_validation import validate_password
            validate_password(password)
        except serializers.ValidationError as e:
            raise serializers.ValidationError({'password': list(e.codes)})
        data.pop('password2', None)
        return data

    @transaction.atomic
    def save(self, request):
        """
        Создает пользователя, используя наш CustomUserManager и отправляет письмо
        с кастомной ссылкой верификации, ведущей на фронтенд (с учетом locale).
        """
        user = User.objects.create_user(
            username=self.validated_data.get('username'),
            email=self.validated_data.get('email'),
            password=self.validated_data.get('password1'),
        )
        user.is_active = not allauth_app_settings.EMAIL_VERIFICATION == allauth_app_settings.EmailVerificationMethod.MANDATORY
        user.save(update_fields=['is_active'])

        try:
            # --- Формируем ссылку для фронтенда вручную С УЧЕТОМ LOCALE ---
            email_address, created = EmailAddress.objects.get_or_create(
                user=user, email=user.email, defaults={'primary': True, 'verified': False}
            )
            if created: logger.info(f"Created EmailAddress record for {user.email}")

            key = EmailConfirmationHMAC(email_address).key
            frontend_url_base = getattr(settings, 'FRONTEND_URL', '')
            if frontend_url_base.endswith('/'):
                 frontend_url_base = frontend_url_base[:-1]

            # Получаем текущий язык из запроса
            current_language = translation.get_language_from_request(request, check_path=True) or settings.LANGUAGE_CODE.split('-')[0] # Запасной язык

            # Собираем URL, используя шаблон из настроек, но подставляя locale
            # Пример шаблона в settings: /auth/confirm-email/{key}/ (без locale)
            path_template_without_locale = getattr(settings, 'ACCOUNT_EMAIL_CONFIRMATION_URL_PATH', '/auth/confirm-email/{key}/')
            # Добавляем locale в начало пути
            activate_relative_path = f"/{current_language}{path_template_without_locale.format(key=key)}"
            activate_url = frontend_url_base + activate_relative_path
            logger.debug(f"Generated activation URL for email (with locale): {activate_url}")
            # -----------------------------------------------------------------

            context = {
                "user": user,
                "activate_url": activate_url, # Передаем нашу ссылку с locale
                "current_site": getattr(settings, 'SITE_ID', 1),
                "key": key,
            }

            adapter = get_adapter(request)
            adapter.send_mail(
                'account/email/email_confirmation',
                user.email,
                context
            )
        except Exception as e:
            logger.error(f"Failed to send verification email to {user.email}: {e}", exc_info=True)

        logger.info(f"User registered via API: {user.username} ({user.email}), needs verification.")
        return user


# --- Кастомный Сериализатор для Запроса Сброса Пароля ---
class CustomPasswordResetSerializer(BasePasswordResetSerializer):
    @property
    def password_reset_form_class(self):
        return CustomResetPasswordForm


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

# --- Сериализатор для Подтверждения Email (НОВЫЙ) ---
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


class MedicalTestSubmissionDetailSerializer(serializers.ModelSerializer):
    """
    Сериализатор для детального просмотра одной загрузки, включая вложенные результаты тестов.
    """
    test_type_name = serializers.CharField(source='test_type.name', read_only=True, allow_null=True)
    file_name = serializers.SerializerMethodField()
    # Вложенный сериализатор для результатов, связанных с этой загрузкой
    # related_name='results' в модели MedicalTestSubmission позволяет получить их через submission.results.all()
    results = AnalyteHistoryResultSerializer(many=True, read_only=True) # Используем существующий сериализатор результатов

    class Meta:
        model = MedicalTestSubmission
        fields = [
            'id', 'user', 'test_type', 'test_type_name', 'submission_date',
            'test_date', 'notes', 'uploaded_file', 'file_name',
            'processing_status', 'processing_details', 'extracted_text',
            'created_at', 'updated_at',
            'results', # Включаем вложенные результаты
        ]
        read_only_fields = fields # Все поля только для чтения

    def get_file_name(self, obj):
        if obj.uploaded_file:
            import os
            return os.path.basename(obj.uploaded_file.name)
        return None
