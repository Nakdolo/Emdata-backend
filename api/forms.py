# ==============================================================================
# Файл: api/forms.py
# Описание: Кастомные формы для API.
# ==============================================================================

from django import forms
from django.urls import reverse
# Импортируем базовую форму сброса пароля из allauth
from allauth.account.forms import ResetPasswordForm as AllauthResetPasswordForm
# Импортируем утилиты allauth для генерации токена и ссылки
from allauth.account.utils import user_pk_to_url_str, user_username
from allauth.account.adapter import get_adapter
from allauth.utils import build_absolute_uri
# Импортируем настройки
from django.conf import settings
# Импортируем функцию для получения языка из запроса
from django.utils import translation

class CustomResetPasswordForm(AllauthResetPasswordForm):
    """
    Переопределяем стандартную форму сброса пароля allauth,
    чтобы генерировать правильную ссылку для фронтенда, ВКЛЮЧАЯ ЯЗЫК (locale).
    """

    def save(self, request, **kwargs):
        """
        Переопределенный метод save.
        Находит пользователей по email и отправляет им письмо
        со ссылкой на фронтенд, включающей locale, uid и token.
        """
        email = self.cleaned_data['email']
        token_generator = kwargs.get('token_generator')

        for user in self.users:
            temp_key = token_generator.make_token(user)

            # --- Генерируем URL для ФРОНТЕНДА с учетом языка ---
            # Получаем текущий язык из запроса
            current_language = translation.get_language_from_request(request, check_path=True)
            # Формируем относительный путь для фронтенда
            # Используем путь, который ты указал: /<locale>/password-reset/<uid>/<token>/
            relative_path = f"/{current_language}/password-reset/{user_pk_to_url_str(user)}/{temp_key}/"

            # Собираем полный URL, используя FRONTEND_URL из настроек
            # Убедись, что FRONTEND_URL в settings.py не содержит слеша в конце
            # (например, FRONTEND_URL = 'http://localhost:3000')
            frontend_url_base = getattr(settings, 'FRONTEND_URL', '') # Получаем базовый URL фронта
            # Убираем возможный слеш в конце базового URL
            if frontend_url_base.endswith('/'):
                 frontend_url_base = frontend_url_base[:-1]
            # Собираем финальный URL
            url = frontend_url_base + relative_path
            # -----------------------------------------------------------

            context = {
                'user': user,
                'password_reset_url': url, # <-- Передаем наш кастомный URL в шаблон
                'request': request,
            }

            # Отправляем email, используя стандартный адаптер allauth и стандартные шаблоны
            get_adapter(request).send_mail(
                'account/email/password_reset_key', # Имя шаблона письма
                email,
                context
            )

        return email
