# ==============================================================================
# Файл: users/adapter.py
# Описание: Кастомный адаптер для django-allauth.
# ==============================================================================
import logging
from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)

class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Кастомный адаптер для переопределения поведения allauth.
    """

    def confirm_email(self, request, email_address):
        """
        Вызывается, когда email успешно подтвержден.
        Мы переопределяем его, чтобы гарантированно активировать пользователя.
        """
        # Вызываем стандартную логику подтверждения (она помечает EmailAddress как verified)
        email_address.verified = True
        email_address.set_as_primary(conditional=True)
        email_address.save()

        # --- ЯВНО АКТИВИРУЕМ ПОЛЬЗОВАТЕЛЯ ---
        user = email_address.user
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=['is_active'])
            logger.info(f"User {user.username} activated via email confirmation.")
        # -----------------------------------

        # Стандартная логика отправки сигнала (оставляем на всякий случай)
        from allauth.account.signals import email_confirmed
        email_confirmed.send(
            sender=self.__class__,
            request=request,
            email_address=email_address,
        )


    # Пример: переопределение URL после подтверждения email (можно раскомментировать, если нужно)
    # def get_email_confirmation_redirect_url(self, request, emailconfirmation):
    #     """
    #     URL для перенаправления после успешного подтверждения email.
    #     """
    #     # Перенаправляем на страницу входа или на специальную страницу успеха
    #     return reverse("account_login") + "?verified=true" # Добавляем параметр для сообщения

    # Пример: отключение регистрации (если нужно)
    # def is_open_for_signup(self, request):
    #     return False

    # Добавьте сюда другие методы DefaultAccountAdapter для кастомизации,
    # если это необходимо в будущем.
    # pass # Убираем pass, так как добавили метод

