from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, UserProfile

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Профиль'
    fk_name = 'user'
    fields = ('date_of_birth', 'phone_number', 'bio', 'profile_picture')

class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    # Используем username в отображении и поиске
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'groups')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    fieldsets = (
        (None, {'fields': ('username', 'password')}), # Добавляем username
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}), # Переносим email сюда
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = ( # Поля для формы создания суперпользователя
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password', 'password2'),
        }),
    )

    def get_inline_instances(self, request, obj=None):
        if not obj: return list()
        return super().get_inline_instances(request, obj)

admin.site.register(User, CustomUserAdmin)