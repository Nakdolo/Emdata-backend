# ==============================================================================
# Файл: health_project/settings.py (Финальная версия)
# ==============================================================================
import os
from pathlib import Path
from dotenv import load_dotenv
from django.urls import reverse_lazy # Не используется напрямую здесь, но может пригодиться

load_dotenv() # Загрузка переменных из .env

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-fallback-key-for-dev')
DEBUG = os.getenv('DJANGO_DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites', # <-- Обязательно для Allauth

    # Сторонние приложения
    'rest_framework',
    'rest_framework.authtoken', # Для Token Authentication
    'corsheaders',              # Для CORS
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'dj_rest_auth',
    'dj_rest_auth.registration',
    'drf_yasg',                 # Для документации API

    # Ваши приложения
    'users.apps.UsersConfig',
    'data.apps.DataConfig',
    'api.apps.ApiConfig',       # Убедись, что создано
]

SITE_ID = 1 # Обязательно для Allauth

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware', # <-- Должен быть ВЫШЕ CommonMiddleware
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware', # <-- Middleware для Allauth
]

ROOT_URLCONF = 'health_project.urls' # Главный urls.py

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # Общая папка шаблонов (для переопределения allauth)
        'APP_DIRS': True, # Искать шаблоны в приложениях
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'health_project.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# Internationalization
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Asia/Almaty'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [ BASE_DIR / "static", ] # Убедись, что папка 'static' существует

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Custom User Model ---
AUTH_USER_MODEL = 'users.User' # Наша кастомная модель

# --- Django REST Framework Settings ---
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
}

# --- Адрес твоего фронтенда ---
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000') # Убедись, что без слеша в конце

# --- dj-rest-auth Settings ---
REST_AUTH = {
    'REGISTER_SERIALIZER': 'api.serializers.CustomRegisterSerializer',
    'USER_DETAILS_SERIALIZER': 'api.serializers.UserSerializer',
    'LOGIN_SERIALIZER': 'dj_rest_auth.serializers.LoginSerializer',
    'PASSWORD_RESET_SERIALIZER': 'api.serializers.CustomPasswordResetSerializer', # Используем кастомный для генерации ссылки
    'PASSWORD_RESET_CONFIRM_SERIALIZER': 'dj_rest_auth.serializers.PasswordResetConfirmSerializer', # Стандартный для подтверждения
    # PASSWORD_RESET_CONFIRM_URL больше не нужна здесь, т.к. форма генерирует URL
}

# --- Django Allauth Settings ---
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
)

ACCOUNT_AUTHENTICATION_METHOD = 'username_email' # Вход по username ИЛИ email
ACCOUNT_USER_MODEL_USERNAME_FIELD = 'username'   # Используем поле username
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'         # Требовать подтверждение email
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = False      # Не входить автоматически после подтверждения
ACCOUNT_ADAPTER = 'users.adapter.CustomAccountAdapter' # Наш адаптер (для активации пользователя)
ACCOUNT_LOGIN_METHODS = ['username', 'email']    # Разрешенные методы входа
ACCOUNT_SIGNUP_FIELDS = ['username*', 'email*']  # Обязательные поля для регистрации (формат allauth)
ACCOUNT_RATE_LIMITS = { "login_failed": "5/5m", } # Ограничение попыток входа
ACCOUNT_LOGOUT_ON_GET = True                     # Разрешить выход GET-запросом

# --- Настройка URL для подтверждения Email (ТОЛЬКО ОТНОСИТЕЛЬНЫЙ ПУТЬ) ---
# {key} будет заменен на ключ подтверждения
# Язык и базовый URL фронтенда будут добавлены в CustomRegisterSerializer
ACCOUNT_EMAIL_CONFIRMATION_URL_PATH = "/confirm-email/{key}/" # <-- Путь на фронтенде
# -----------------------------------------------------------------

# URL для страницы, куда перенаправлять ПОСЛЕ успешного подтверждения email
ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = FRONTEND_URL + '/login?verified=true' # На страницу входа
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = FRONTEND_URL + '/profile?verified=true' # На страницу профиля (если пользователь уже вошел)

# Email Settings
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend' # Письма в консоль
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.getenv('EMAIL_HOST')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'webmaster@localhost')

# URL для перенаправления (для стандартных Django/Allauth веб-форм)
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'

# --- Настройки CORS ---
CORS_ALLOW_ALL_ORIGINS = True
# CORS_ALLOW_ALL_ORIGINS = True # Для отладки
CORS_ALLOW_HEADERS = [
    "accept", "authorization", "content-type", "user-agent",
    "x-csrftoken", "x-requested-with",
]
# CORS_ALLOW_CREDENTIALS = True # Если используешь cookies

# Настройки логирования
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': { 'verbose': { 'format': '{levelname} [{asctime}] [{module}:{lineno}] {message}', 'style': '{', }, },
    'handlers': { 'console': { 'class': 'logging.StreamHandler', 'formatter': 'verbose', }, },
    'loggers': {
        'django': { 'handlers': ['console'], 'level': 'INFO', 'propagate': True, }, # Оставляем DEBUG для отладки
        'users': { 'handlers': ['console'], 'level': 'DEBUG' if DEBUG else 'INFO', 'propagate': False, },
        'data': { 'handlers': ['console'], 'level': 'DEBUG' if DEBUG else 'INFO', 'propagate': False, },
        'data.tasks': { 'handlers': ['console'], 'level': 'DEBUG' if DEBUG else 'INFO', 'propagate': False, },
        'api': { 'handlers': ['console'], 'level': 'DEBUG' if DEBUG else 'INFO', 'propagate': False, },
        'allauth': { 'handlers': ['console'], 'level': 'DEBUG', 'propagate': True, }, # Оставляем DEBUG для отладки allauth
    },
}
