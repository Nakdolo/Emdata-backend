from django.contrib import admin
# Импортируем только существующие модели
from .models import TestType, MedicalTestSubmission, Analyte, TestResult

@admin.register(TestType)
class TestTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Analyte)
class AnalyteAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit', 'name_en', 'name_ru', 'name_kk', 'abbreviations')
    search_fields = ('name', 'name_en', 'name_ru', 'name_kk', 'abbreviations')
    list_filter = ('unit',)
    fieldsets = (
        (None, {'fields': ('name', 'unit', 'description')}),
        ('Localization & Aliases', {'fields': ('name_en', 'name_ru', 'name_kk', 'abbreviations')}),
    )

class TestResultInline(admin.TabularInline):
    """ Инлайн для отображения результатов на странице загрузки """
    model = TestResult
    fields = ('analyte', 'value', 'value_numeric', 'unit', 'reference_range', 'is_abnormal')
    readonly_fields = ('analyte', 'value', 'value_numeric', 'unit', 'reference_range', 'is_abnormal', 'extracted_at') # Делаем поля только для чтения
    extra = 0 # Не показывать пустые формы для добавления
    can_delete = False # Запрещаем удаление результатов через админку загрузки

    def has_add_permission(self, request, obj=None):
        return False # Запрещаем добавление результатов через админку загрузки

@admin.register(MedicalTestSubmission)
class MedicalTestSubmissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_email', 'test_type', 'submission_date', 'test_date', 'processing_status', 'result_count')
    list_filter = ('processing_status', 'test_type', 'submission_date')
    search_fields = ('user__email', 'id', 'uploaded_file')
    readonly_fields = ('user', 'submission_date', 'created_at', 'updated_at', 'extracted_text', 'processing_details') # Делаем основные поля неизменяемыми
    list_select_related = ('user', 'test_type') # Оптимизация запроса
    inlines = [TestResultInline] # Добавляем инлайн с результатами

    fieldsets = (
        (None, {'fields': ('id', 'user', 'submission_date')}),
        ('Test Info', {'fields': ('test_type', 'test_date', 'notes', 'uploaded_file')}),
        ('Processing', {'fields': ('processing_status', 'processing_details', 'extracted_text')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'

    def result_count(self, obj):
        return obj.results.count()
    result_count.short_description = 'Results'

    # Запрещаем редактирование через админку после создания (кроме статуса, если нужно)
    # def get_readonly_fields(self, request, obj=None):
    #     if obj: # editing an existing object
    #         return self.readonly_fields + ('test_type', 'test_date', 'notes', 'uploaded_file')
    #     return self.readonly_fields

