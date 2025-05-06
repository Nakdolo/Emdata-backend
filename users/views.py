# ==============================================================================
# Файл: users/views.py
# Описание: Представления Django для приложения users.
# ==============================================================================

import logging
from django.shortcuts import redirect
from django.urls import reverse_lazy
from allauth.account.views import ConfirmEmailView, EmailVerificationSentView
from allauth.account.models import EmailConfirmationHMAC

logger = logging.getLogger(__name__)

# --- Кастомное Представление для Подтверждения Email ---
class CustomConfirmEmailView(ConfirmEmailView):
    """
    Кастомное представление для страницы подтверждения email.
    Можно переопределить template_name или добавить свою логику.
    """
    # template_name = 'users/custom_email_confirm.html' # Если нужен свой шаблон

    def get_context_data(self, **kwargs):
        # Добавляем обработку случая, если ключ не найден стандартным методом
        context = super().get_context_data(**kwargs)
        if 'confirmation' not in context and 'key' in self.kwargs:
            logger.debug(f"Standard confirmation not found for key: {self.kwargs['key']}. Trying HMAC.")
            try:
                # Пытаемся получить подтверждение через HMAC (стандартный способ allauth)
                context['confirmation'] = EmailConfirmationHMAC.from_key(self.kwargs['key'])
                if context['confirmation']:
                     logger.debug(f"HMAC confirmation object found for key: {self.kwargs['key']}")
                else:
                     logger.warning(f"HMAC confirmation object is None for key: {self.kwargs['key']}")

            except Exception as e:
                logger.error(f"Error creating EmailConfirmationHMAC from key {self.kwargs['key']}: {e}")
                context['confirmation'] = None # Устанавливаем None, если ключ невалиден
        elif 'confirmation' in context:
             logger.debug(f"Standard confirmation object found: {context['confirmation']}")
        else:
             logger.warning("No key found in kwargs for email confirmation.")

        return context

    def post(self, *args, **kwargs):
        # Стандартная логика allauth должна обработать POST для подтверждения
        # Можно добавить свою логику после вызова super().post()
        logger.info(f"POST request to confirm email with key: {self.kwargs.get('key')}")
        response = super().post(*args, **kwargs)
        # После успешного подтверждения allauth обычно перенаправляет.
        # Если нужно свое перенаправление:
        # if response.status_code == 302 and self.object and self.object.email_address.verified:
        #     logger.info(f"Email {self.object.email_address.email} confirmed successfully. Redirecting.")
        #     return redirect('my_custom_success_url') # Пример
        return response

# --- Кастомное Представление для Страницы "Письмо Отправлено" ---
class CustomEmailVerificationSentView(EmailVerificationSentView):
    """
    Кастомное представление для страницы, информирующей об отправке письма.
    Можно переопределить template_name.
    """
    template_name = 'account/verification_sent.html' # Используем стандартный шаблон allauth
    # Или ваш кастомный: template_name = 'users/custom_verification_sent.html'

    # Можно добавить дополнительный контекст, если нужно
    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     context['my_extra_info'] = "Some additional info"
    #     return context

# --- Другие представления для users (если нужны) ---
# Например, представление для редактирования профиля
# from django.views.generic import UpdateView
# from django.contrib.auth.mixins import LoginRequiredMixin
# from .models import UserProfile
# from .forms import UserProfileForm # Нужно будет создать форму

# class ProfileUpdateView(LoginRequiredMixin, UpdateView):
#     model = UserProfile
#     form_class = UserProfileForm
#     template_name = 'users/profile_edit.html'
#     success_url = reverse_lazy('profile_view') # URL для просмотра профиля

#     def get_object(self, queryset=None):
#         # Получаем профиль текущего пользователя
#         return self.request.user.profile

