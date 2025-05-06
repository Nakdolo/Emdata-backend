import uuid
from django.contrib.auth.models import AbstractUser, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .managers import CustomUserManager # Импортируем менеджер

class User(AbstractUser, PermissionsMixin):
    username = models.CharField(
        _('username'), max_length=150, unique=True,
        help_text=_('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
        validators=[AbstractUser.username_validator],
        error_messages={ 'unique': _("A user with that username already exists."), },
    )
    email = models.EmailField(_('email address'), unique=True, blank=False)
    first_name = models.CharField(_('first name'), max_length=150, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    is_staff = models.BooleanField(_('staff status'), default=False, help_text=_('Designates whether the user can log into this admin site.'),)
    is_active = models.BooleanField(_('active'), default=True, help_text=_('Designates whether this user should be treated as active. Unselect this instead of deleting accounts.'),)
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email'] # Email обязателен при создании суперпользователя

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    objects = CustomUserManager() # Используем кастомный менеджер

    def __str__(self):
        return self.username

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='profile')
    date_of_birth = models.DateField(_("Date of Birth"), null=True, blank=True)
    phone_number = models.CharField(_("Phone Number"), max_length=20, blank=True, null=True)
    bio = models.TextField(_("About Me"), blank=True, null=True)
    profile_picture = models.ImageField(_("Profile Picture"), upload_to='profile_pics/%Y/%m/%d/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile for {self.user.username}"

    class Meta:
        verbose_name = _("User Profile")
        verbose_name_plural = _("User Profiles")

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        UserProfile.objects.get_or_create(user=instance)