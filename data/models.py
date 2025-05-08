# ==============================================================================
# Файл: data/models.py
# Описание: Модели базы данных Django для медицинских данных.
# ==============================================================================
import uuid
import logging
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.utils.text import slugify
from decimal import Decimal

User = settings.AUTH_USER_MODEL
logger = logging.getLogger(__name__)

class TestType(models.Model):
    """Тип медицинского анализа (например, ОАК, Биохимия)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Test Type Name"), max_length=100, unique=True)
    description = models.TextField(_("Description"), blank=True, null=True)
    keywords = models.CharField(
        _("Keywords for Identification"),
        max_length=255, blank=True, null=True,
        help_text=_("Comma-separated keywords found in PDF titles or headers (e.g., ОАК,CBC,Биохимия)")
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Test Type")
        verbose_name_plural = _("Test Types")
        ordering = ['name']


class MedicalTestSubmission(models.Model):
    """Загрузка файла медицинского анализа пользователем."""
    class StatusChoices(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        PROCESSING = 'PROCESSING', _('Processing')
        COMPLETED = 'COMPLETED', _('Completed')
        FAILED = 'FAILED', _('Failed')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='test_submissions', verbose_name=_("User"))
    test_type = models.ForeignKey(
        TestType,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='submissions', verbose_name=_("Test Type")
    )
    submission_date = models.DateTimeField(_("Submission Date"), default=timezone.now)
    test_date = models.DateField(_("Test Date"), null=True, blank=True, help_text=_("Date the test was performed, if known."))
    notes = models.TextField(_("User Notes"), blank=True, null=True)
    uploaded_file = models.FileField(
        _("Uploaded File"),
        upload_to='medical_tests/%Y/%m/%d/',
        null=False, blank=False
    )
    processing_status = models.CharField(
        _("Processing Status"), max_length=20, choices=StatusChoices.choices,
        default=StatusChoices.PENDING, db_index=True
    )
    processing_details = models.TextField(_("Processing Details"), blank=True, null=True, help_text=_("Logs or error messages from processing."), max_length=4000)
    extracted_text = models.TextField(_("Extracted Text"), blank=True, null=True, help_text=_("Raw text extracted from the uploaded file."))
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    def __str__(self):
        test_type_name = self.test_type.name if self.test_type else _('Unknown Type')
        user_identifier = self.user.email
        return f"{test_type_name} submission for {user_identifier} on {self.submission_date.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        verbose_name = _("Medical Test Submission")
        verbose_name_plural = _("Medical Test Submissions")
        ordering = ['-submission_date']


class Analyte(models.Model):
    """Отдельный показатель (аналит), измеряемый в тесте."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Analyte Name (Primary)"), max_length=150, unique=True, db_index=True, help_text=_("Primary name used internally or for default display."))
    name_en = models.CharField(_("English Name"), max_length=150, blank=True, db_index=True)
    name_ru = models.CharField(_("Russian Name"), max_length=150, blank=True, db_index=True)
    name_kk = models.CharField(_("Kazakh Name"), max_length=150, blank=True, db_index=True)
    abbreviations = models.CharField(
        _("Abbreviations (comma-separated)"), max_length=500,
        blank=True, help_text=_("Common abbreviations, e.g., Hb, Hgb, HCT, Plt, АЛТ, АСТ, ТТГ")
    )
    unit = models.CharField(_("Standard Unit"), max_length=50, help_text=_("Default unit if not found in the report."))
    description = models.TextField(_("Description"), blank=True, null=True)
    typical_test_types = models.ManyToManyField(
        TestType,
        related_name='typical_analytes',
        blank=True,
        verbose_name=_("Typical Test Types")
    )

    def get_all_names(self):
        """Возвращает список всех известных имен и аббревиатур в нижнем регистре."""
        names = set()
        for name_field in [self.name, self.name_en, self.name_ru, self.name_kk]:
            if name_field:
                names.add(name_field.strip().lower())
        if self.abbreviations:
            abbrs = [abbr.strip().lower() for abbr in self.abbreviations.split(',') if abbr.strip()]
            names.update(abbrs)
        return list(filter(None, names))

    def __str__(self):
        return f"{self.name} ({self.unit})"

    class Meta:
        verbose_name = _("Analyte")
        verbose_name_plural = _("Analytes")
        ordering = ['name']


class TestResult(models.Model):
    """Результат конкретного анализа для конкретной загрузки."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(MedicalTestSubmission, on_delete=models.CASCADE, related_name='results', verbose_name=_("Submission"))
    analyte = models.ForeignKey(Analyte, on_delete=models.PROTECT, related_name='results', verbose_name=_("Analyte"))
    value = models.CharField(_("Reported Value"), max_length=100, help_text=_("The exact value string found in the report."))
    value_numeric = models.DecimalField(
        _("Numeric Value"), max_digits=14, decimal_places=4, null=True, blank=True,
        help_text=_("Numeric representation of the value for calculations.")
    )
    unit = models.CharField(_("Reported Unit"), max_length=50, blank=True, help_text=_("Unit found in the report, might differ from standard."))
    reference_range = models.CharField(_("Reference Range"), max_length=150, blank=True, null=True, help_text=_("Reference range string from the report."))
    # Поле для хранения текстового статуса из PDF
    status_text = models.CharField(
        _("Status Text"), max_length=100, blank=True, null=True, # <-- НОВОЕ ПОЛЕ
        help_text=_("Status text found in the report (e.g., 'В норме', 'Ниже нормы').")
    )
    is_abnormal = models.BooleanField(
        _("Is Abnormal?"), null=True, blank=True, db_index=True, # Оставляем для простой фильтрации
        help_text=_("Indicates if the value falls outside the reference range or marked as abnormal.")
    )
    extracted_at = models.DateTimeField(_("Extracted At"), default=timezone.now)

    def __str__(self):
        unit_display = self.unit or self.analyte.unit or ''
        status_display = f" ({self.status_text})" if self.status_text else ""
        return f"{self.analyte.name}: {self.value} {unit_display}{status_display}"

    class Meta:
        verbose_name = _("Test Result")
        verbose_name_plural = _("Test Results")
        ordering = ['submission__submission_date', 'analyte__name']
        unique_together = ('submission', 'analyte')



class HealthSummary(models.Model):
    """
    Хранит резюме состояния здоровья, сгенерированное AI, и связанную информацию.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='health_summaries', verbose_name=_("User"))
    created_at = models.DateTimeField(_("Created At"), default=timezone.now)
    
    # Входные данные для AI
    symptoms_prompt = models.TextField(_("User Symptoms Prompt"), blank=True, help_text=_("Symptoms provided by the user."))
    analyte_data_snapshot = models.JSONField(_("Analyte Data Snapshot"), null=True, blank=True, help_text=_("JSON snapshot of analyte data used for this summary."))

    # Ответ от AI (или симуляции)
    ai_raw_response = models.TextField(_("AI Raw Response"), blank=True, null=True, help_text=_("Full response from the AI model, if available."))
    ai_summary = models.TextField(_("AI Overall Summary"), blank=True)
    ai_key_findings = models.JSONField(_("AI Key Findings"), default=list, blank=True, help_text=_("List of key findings strings."))
    ai_detailed_breakdown = models.JSONField(_("AI Detailed Breakdown"), default=list, blank=True, help_text=_("List of objects detailing metric changes and comments."))
    ai_suggested_diagnosis = models.CharField(_("AI Suggested Diagnosis"), max_length=255, blank=True)

    # Подтверждение диагноза (для будущей реализации)
    is_confirmed = models.BooleanField(_("Is Confirmed?"), default=False, db_index=True)
    confirmed_diagnosis = models.CharField(_("Confirmed Diagnosis"), max_length=255, blank=True, null=True)
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_summaries', verbose_name=_("Confirmed By"))
    confirmed_at = models.DateTimeField(_("Confirmed At"), null=True, blank=True)

    def __str__(self):
        user_identifier = getattr(self.user, self.user.EMAIL_FIELD, self.user.get_username())
        return f"Health Summary for {user_identifier} on {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        verbose_name = _("Health Summary")
        verbose_name_plural = _("Health Summaries")
        ordering = ['-created_at']
