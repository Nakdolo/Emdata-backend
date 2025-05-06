import logging
import threading
import re
from decimal import Decimal, InvalidOperation, Context, ROUND_HALF_UP
import pdfplumber
from django.db import transaction, OperationalError, models
from django.utils import timezone
from django.conf import settings
from collections import Counter
import datetime
from dateutil.parser import parse as date_parse
from dateutil.parser._parser import ParserError

from .models import MedicalTestSubmission, TestResult, Analyte, TestType

task_logger = logging.getLogger('data.tasks')

# --- Скомпилированные Регулярные Выражения (Оптимизация) ---
UNIT_PATTERNS_LIST = [
    r'г/л', r'g/l', r'г/дл', r'g/dl', r'%', r'проц\.?', r'фл', r'f[lL]', r'пг', r'pg',
    r'млн[./\s]?мкл', r'млн[./\s]?мка', r'x\s?10\^?12[/]?л', r'10\^?12[/]?л', r'10\s?\*\s?12[/]?л', r'х\s?10\s?\*\s?12[/]?л',
    r'тыс[./\s]?мкл', r'тыс[./\s]?мка', r'x\s?10\^?9[/]?л', r'10\^?9[/]?л', r'10\s?\*\s?9[/]?л', r'х\s?10\s?\*\s?9[/]?л',
    r'сек', r'с', r'seconds?', r'нг/мл', r'ng/ml', r'мкг/л', r'ug/l', r'мкг/дл', r'ug/dl',
    r'мкмоль/л', r'µmol/l', r'umol/l', r'ммоль/л', r'mmol/l', r'Ед/л', r'U/L', r'Е/л',
    r'IU/L', r'МЕ/л', r'МЕ/мл', r'мМЕ/л', r'mIU/L', r'мкМЕ/мл', r'uIU/mL', r'мг/дл',
    r'mg/dl', r'мг/л', r'mg/l', r'мг/сут', r'г/сут', r'мм/час', r'mm/hr', r'мм/ч',
    r'пмоль/л', r'pmol/l', r'нмоль/л', r'nmol/l', r'пг/мл', r'мкг/мл', r'КОЕ/мл',
    r'CFU/ml', r'титр', r'индекс', r'ratio', r'отн\.?\s*ед\.?', r'в п/з', r'/hpf', r'/lpf',
    r'мл/мин', r'ml/min', r'мм',
]
UNIT_PATTERN_COMPILED = re.compile(r'(?i)\b(' + '|'.join(UNIT_PATTERNS_LIST) + r')\b')

REF_PATTERNS_LIST = [
     r'(\d+\.?\d*\s*-\s*\d+\.?\d*)',         # X - Y
     r'(<|<=|>|>=)\s*(\d+\.?\d*)',           # <X, <=X, >X, >=X
     r'\((\d+\.?\d*\s*-\s*\d+\.?\d*)\)',      # (X - Y)
     r'\[(\d+\.?\d*\s*-\s*\d+\.?\d*)\]',      # [X - Y]
     r'\((<|<=|>|>=)\s*\d+\.?\d*\)',          # (<X) или (>X)
]
REF_PATTERN_COMPILED = re.compile(r'(?i)(?:' + '|'.join(REF_PATTERNS_LIST) + r')')

VALUE_PATTERN_COMPILED = re.compile(r'([-+]?\d+([.,]\d+)?)')
POTENTIAL_RESULT_PATTERN_COMPILED = re.compile(r'([a-zA-Zа-яА-ЯёЁ\s\(\)\-]+)\s+([-+]?\d+([.,]\d+)?).*(?:(\d+\.?\d*\s*-\s*\d+\.?\d*)|(<|<=|>|>=)\s*(\d+\.?\d*))?')

# Паттерны для текстового статуса
STATUS_TEXT_PATTERNS = [
    r'(В норме)', r'(Норма)',
    r'(Ниже нормы)', r'(Выше нормы)',
    r'(Патология)', r'(Отклонение)',
    r'(Положительно)', r'(Отрицательно)',
    r'(Обнаружено)', r'(Не обнаружено)',
    # Добавь другие варианты, если нужно
]
STATUS_TEXT_PATTERN_COMPILED = re.compile(r'(?i)\b(' + '|'.join(STATUS_TEXT_PATTERNS) + r')\s*$') # Ищем в конце строки


# --- Вспомогательные Функции Парсинга ---

def parse_reference_range(range_str):
    # (Код без изменений)
    if not range_str: return None, None
    range_str = str(range_str).strip().replace(',', '.')
    lower_bound, upper_bound = None, None
    decimal_context = Context(prec=14)
    match = re.match(r'^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\b', range_str)
    if match:
        try:
            lower_bound = decimal_context.create_decimal(match.group(1))
            upper_bound = decimal_context.create_decimal(match.group(2))
            return lower_bound, upper_bound
        except InvalidOperation: pass
    match = re.match(r'^\s*(<|<=)\s*(\d+(?:\.\d+)?)\b', range_str)
    if match:
        try:
            upper_bound = decimal_context.create_decimal(match.group(2))
            return None, upper_bound
        except InvalidOperation: pass
    match = re.match(r'^\s*(>|>=)\s*(\d+(?:\.\d+)?)\b', range_str)
    if match:
        try:
            lower_bound = decimal_context.create_decimal(match.group(2))
            return lower_bound, None
        except InvalidOperation: pass
    match = re.match(r'^\s*0\s*-\s*(\d+(?:\.\d+)?)\b', range_str)
    if match:
        try:
            lower_bound = Decimal('0')
            upper_bound = decimal_context.create_decimal(match.group(1))
            return lower_bound, upper_bound
        except InvalidOperation: pass
    task_logger.warning(f"Reference range format not recognized or parsed: '{range_str}'")
    return None, None

def find_value(segment):
    """Ищет первое числовое значение в сегменте строки."""
    value_match = VALUE_PATTERN_COMPILED.search(segment)
    if value_match:
        value_str = value_match.group(1).replace(',', '.')
        task_logger.debug(f"  Helper find_value: Found '{value_str}'")
        return value_str, value_match.end()
    task_logger.debug(f"  Helper find_value: No value found in '{segment}'")
    return None, -1

def find_unit(segment, default_unit):
    """Ищет первую единицу измерения в сегменте строки."""
    unit_match = UNIT_PATTERN_COMPILED.search(segment)
    if unit_match:
        unit_str = unit_match.group(1)
        # Нормализация
        if unit_str.lower() in ['тыс/мка', 'тыс/мкл', 'тыс./мкл']: unit_str = 'x10^9/л'
        if unit_str.lower() in ['млн/мка', 'млн/мкл', 'млн./мкл']: unit_str = 'x10^12/л'
        if unit_str.lower() in ['мм/ч']: unit_str = 'мм/час'
        if unit_str.lower() in ['г/дл']: unit_str = 'g/dL'
        if unit_str.lower() in ['пг']: unit_str = 'pg'
        task_logger.debug(f"    Helper find_unit: Found '{unit_str}'")
        return unit_str
    task_logger.debug(f"    Helper find_unit: Not found in '{segment}', using default '{default_unit}'")
    return default_unit

def find_reference_range(segment):
    """Ищет первый референсный диапазон в сегменте строки."""
    ref_match = REF_PATTERN_COMPILED.search(segment)
    if ref_match:
        potential_range = next((g for g in ref_match.groups()[::-1] if g), ref_match.group(0))
        if potential_range:
            cleaned_range = potential_range.strip().replace('(', '').replace(')', '').replace('[', '').replace(']', '')
            if re.search(r'\d', cleaned_range):
                task_logger.debug(f"    Helper find_reference_range: Found '{cleaned_range}'")
                return cleaned_range
            else:
                task_logger.debug(f"    Helper find_reference_range: Potential match '{cleaned_range}' ignored (no digits).")
    task_logger.debug(f"    Helper find_reference_range: Not found in '{segment}'.")
    return None

def find_status_text(line):
    """Ищет текстовый статус в конце строки."""
    status_match = STATUS_TEXT_PATTERN_COMPILED.search(line)
    if status_match:
        status_text = status_match.group(1).strip()
        task_logger.debug(f"    Helper find_status_text: Found status text '{status_text}'")
        # Определяем is_abnormal на основе текста
        is_abnormal = None
        if status_text.lower() in ['в норме', 'норма', 'отрицательно', 'не обнаружено']:
            is_abnormal = False
        elif status_text.lower() in ['ниже нормы', 'выше нормы', 'патология', 'отклонение', 'положительно', 'обнаружено']:
            is_abnormal = True
        return status_text, is_abnormal
    task_logger.debug(f"    Helper find_status_text: No status text found.")
    return None, None


# --- Функция определения типа теста ---
def determine_test_type(found_analyte_ids):
    # (Код без изменений)
    if not found_analyte_ids:
        task_logger.warning("Cannot determine test type: no analytes found.")
        return None
    task_logger.debug(f"Attempting to determine test type from {len(found_analyte_ids)} found analyte IDs.")
    try:
        test_types = TestType.objects.prefetch_related('typical_analytes').all()
        if not test_types.exists():
            task_logger.warning("No TestTypes found in the database.")
            return None
        type_scores = Counter()
        found_set = set(found_analyte_ids)
        for test_type in test_types:
            typical_ids = set(test_type.typical_analytes.values_list('id', flat=True))
            if not typical_ids: continue
            intersection_count = len(found_set.intersection(typical_ids))
            match_percentage = (intersection_count / len(typical_ids)) * 100 if typical_ids else 0
            type_scores[test_type] = match_percentage
            task_logger.debug(f"  TestType '{test_type.name}': Found {intersection_count}/{len(typical_ids)} typical analytes ({match_percentage:.1f}%)")
        if not type_scores:
             task_logger.warning("No test types with associated typical analytes found.")
             return None
        threshold = 50.0
        best_match_type = None
        highest_score = -1
        for test_type, score in type_scores.items():
             if score >= threshold and score > highest_score:
                 highest_score = score
                 best_match_type = test_type
        if best_match_type:
            task_logger.info(f"Determined TestType as: {best_match_type.name} (Score: {highest_score:.1f}%)")
            return best_match_type
        else:
            task_logger.warning(f"Could not determine test type meeting threshold ({threshold}%). Max score: {max(type_scores.values()) if type_scores else 0:.1f}%")
            return None
    except Exception as e:
        task_logger.error(f"Error during test type determination: {e}", exc_info=True)
        return None

# --- Функция извлечения даты теста ---
def extract_test_date(text):
    # (Код без изменений)
    date_pattern = r'(\d{1,2}[./-]\d{1,2}[./-]\d{4}|\d{4}[./-]\d{1,2}[./-]\d{1,2})'
    keywords = [
        r'Дата и время взятия биоматериала', r'Биоматериалды алу мерзімі',
        r'Дата взятия', r'Дата анализа', r'Дата исследования',
        r'Test Date', r'Collection Date', r'Дата поступления образца',
        r'Үлгінің келіп түскен күні', r'Дата регистрации заявки',
        r'Жолдаманы тіркеу мерзімі',
    ]
    lines = text.split('\n')
    for i, line in enumerate(lines):
        for keyword in keywords:
            if re.search(keyword, line, re.IGNORECASE):
                task_logger.debug(f"Found keyword '{keyword}' in line: {line}")
                search_area = line + "\n" + "\n".join(lines[i+1:i+3])
                date_match = re.search(date_pattern, search_area)
                if date_match:
                    date_str = date_match.group(1)
                    task_logger.debug(f"Potential date string found: '{date_str}'")
                    try:
                        parsed_date = date_parse(date_str, dayfirst=True).date()
                        if datetime.date(1990, 1, 1) <= parsed_date <= timezone.localdate() + datetime.timedelta(days=1):
                             task_logger.info(f"Extracted test date: {parsed_date}")
                             return parsed_date
                        else:
                             task_logger.warning(f"Parsed date {parsed_date} is outside the plausible range.")
                    except (ParserError, ValueError) as e:
                        task_logger.warning(f"Could not parse date string '{date_str}': {e}")
    task_logger.warning("Could not extract a plausible test date from the PDF text.")
    return None


# --- Основная Функция Обработки PDF (v14) ---
def process_pdf_submission_plain(submission_id):
    task_id = f"thread-{threading.get_ident()}"
    task_logger.info(f"[PDF Task {task_id}] Starting for submission ID: {submission_id}")
    submission = None
    extracted_text = ""
    page_count = 0
    processing_error = None
    parsed_results_count = 0
    parsing_details = []
    created_results_list = []
    found_analyte_ids_for_typing = []
    determined_type = None
    extracted_date = None
    processed_line_indices = set()

    try:
        # --- Получение Объекта Загрузки ---
        try:
            submission = MedicalTestSubmission.objects.select_related('test_type', 'user').get(id=submission_id)
            task_logger.info(f"[PDF Task {task_id}] Found submission {submission.id} for user {submission.user.id}")
        except MedicalTestSubmission.DoesNotExist:
            task_logger.error(f"[PDF Task {task_id}] Submission {submission_id} not found. Aborting.")
            return
        except OperationalError as db_err:
             task_logger.error(f"[PDF Task {task_id}] DB error fetching submission {submission_id}: {db_err}. Aborting.")
             return

        # --- Предварительные Проверки ---
        if not submission.uploaded_file or not hasattr(submission.uploaded_file, 'path') or not submission.uploaded_file.name.lower().endswith('.pdf'):
            error_msg = "No valid PDF file associated with this submission."
            MedicalTestSubmission.objects.filter(id=submission_id).update(
                processing_status=MedicalTestSubmission.StatusChoices.FAILED,
                processing_details=error_msg, updated_at=timezone.now()
            )
            return

        # --- Обновление Статуса на PROCESSING (Атомарно) ---
        updated_count = MedicalTestSubmission.objects.filter(
            id=submission_id,
            processing_status__in=[MedicalTestSubmission.StatusChoices.PENDING, MedicalTestSubmission.StatusChoices.FAILED]
        ).update(
            processing_status=MedicalTestSubmission.StatusChoices.PROCESSING,
            processing_details=f"Task {task_id} started processing...",
            extracted_text="", test_date=None, updated_at=timezone.now()
        )
        if updated_count == 0:
            try:
                current_status = MedicalTestSubmission.objects.get(id=submission_id).processing_status
                task_logger.warning(f"[PDF Task {task_id}] Skipping {submission_id}: Status was '{current_status}'.")
            except MedicalTestSubmission.DoesNotExist:
                 task_logger.error(f"[PDF Task {task_id}] Submission {submission_id} disappeared.")
            return
        submission.refresh_from_db()
        task_logger.info(f"[PDF Task {task_id}] Set status to PROCESSING for {submission_id}.")

        # --- Извлечение Текста из PDF ---
        try:
            pdf_path = submission.uploaded_file.path
            task_logger.info(f"[PDF Task {task_id}] Reading PDF file: {pdf_path}")
            full_text_list = []
            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)
                task_logger.info(f"[PDF Task {task_id}] PDF has {page_count} pages. Extracting text...")
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text(x_tolerance=1.5, y_tolerance=1.5, layout=False) or ""
                    full_text_list.append(page_text)
            extracted_text = "\n<-- Page Break -->\n".join(full_text_list)
            submission.extracted_text = extracted_text
            task_logger.info(f"[PDF Task {task_id}] Text extraction complete. Length: {len(extracted_text)}")
        except FileNotFoundError:
            task_logger.error(f"[PDF Task {task_id}] PDF file not found at path: {submission.uploaded_file.path}", exc_info=True)
            processing_error = f"File Not Found Error: PDF file missing."
            raise
        except Exception as pdf_err:
            task_logger.exception(f"[PDF Task {task_id}] Error reading/extracting PDF {submission_id}: {pdf_err}", exc_info=True)
            processing_error = f"PDF Reading/Extraction Error: {str(pdf_err)[:500]}"
            raise

        # --- Извлечение Даты Теста ---
        if not submission.test_date:
            extracted_date = extract_test_date(extracted_text)
            if extracted_date:
                submission.test_date = extracted_date
                parsing_details.append(f"Extracted Test Date: {extracted_date.strftime('%d.%m.%Y')}")
            else:
                parsing_details.append("Could not extract test date from PDF.")
        else:
            parsing_details.append(f"Test Date was pre-filled by user: {submission.test_date.strftime('%d.%m.%Y')}")

        # Сохраняем извлеченный текст и дату (если нашли)
        submission.save(update_fields=['extracted_text', 'test_date', 'updated_at'])

        # --- Построение Карты Алиасов Аналитов ---
        task_logger.info(f"[PDF Task {task_id}] Building analyte alias map...")
        analyte_map = {}
        try:
            all_analytes = Analyte.objects.prefetch_related('typical_test_types').all()
            for analyte in all_analytes:
                aliases = analyte.get_all_names()
                for alias in aliases:
                    if not alias: continue
                    if alias in analyte_map:
                        existing_analyte = analyte_map[alias]
                        if len(analyte.name) > len(existing_analyte.name):
                            analyte_map[alias] = analyte
                    else:
                        analyte_map[alias] = analyte
            task_logger.info(f"[PDF Task {task_id}] Built map with {len(analyte_map)} unique aliases for {len(all_analytes)} analytes.")
        except Exception as map_build_err:
             task_logger.exception(f"[PDF Task {task_id}] Error building analyte map: {map_build_err}", exc_info=True)
             processing_error = f"Error building analyte map: {str(map_build_err)[:500]}"
             raise

        # --- Парсинг Результатов ---
        task_logger.info(f"[PDF Task {task_id}] Starting result parsing...")
        lines = extracted_text.split('\n')
        sorted_aliases = sorted(analyte_map.keys(), key=len, reverse=True)
        processed_analytes_in_submission = set()

        with transaction.atomic():
            deleted_count, _ = TestResult.objects.filter(submission=submission).delete()
            if deleted_count > 0: task_logger.info(f"[PDF Task {task_id}] Deleted {deleted_count} old results.")

            # --- Основной цикл парсинга известных аналитов ---
            for i, line in enumerate(lines):
                line = line.strip()
                if not line or line == '<-- Page Break -->': continue
                # task_logger.debug(f"Processing Line {i}: '{line}'")

                found_analyte_on_line = None
                matched_alias = None
                match_object = None

                for alias in sorted_aliases:
                    try:
                        pattern = r'(?i)\b' + re.escape(alias) + r'(?=\W|$)'
                        match = re.search(pattern, line)
                    except re.error as re_err:
                         task_logger.error(f"Regex error for alias '{alias}': {re_err}")
                         continue

                    if match:
                        potential_analyte = analyte_map[alias]
                        if potential_analyte.id not in processed_analytes_in_submission:
                            is_part_of_longer_match = False
                            # ... (проверка на частичное совпадение) ...
                            if is_part_of_longer_match: continue

                            task_logger.debug(f"Potential match: Alias='{alias}', Analyte='{potential_analyte.name}' in line {i}")
                            found_analyte_on_line = potential_analyte
                            matched_alias = alias
                            match_object = match
                            break

                if found_analyte_on_line:
                    processed_line_indices.add(i)
                    analyte = found_analyte_on_line
                    match_end_index = match_object.end()
                    task_logger.debug(f"Processing line {i} for analyte: '{analyte.name}' (via '{matched_alias}')")
                    potential_segment = line[match_end_index:].strip()
                    task_logger.debug(f"  Segment after alias: '{potential_segment}'")

                    value_str, value_end_index = find_value(potential_segment)

                    if value_str:
                        try:
                            decimal_context = Context(prec=14, rounding=ROUND_HALF_UP)
                            value_numeric = decimal_context.create_decimal(value_str)
                            search_unit_ref_segment = potential_segment[value_end_index:].strip()

                            ref_range_str = find_reference_range(search_unit_ref_segment)
                            unit_str = find_unit(search_unit_ref_segment, analyte.unit)
                            status_text_from_pdf, is_abnormal_from_text = find_status_text(line) # <-- Ищем текст статуса

                            # --- Определение is_abnormal (Приоритет у текста) ---
                            is_abnormal_flag = is_abnormal_from_text
                            if is_abnormal_flag is None and ref_range_str and value_numeric is not None:
                                lower_bound, upper_bound = parse_reference_range(ref_range_str)
                                task_logger.debug(f"    Parsed range bounds: Lower={lower_bound}, Upper={upper_bound}")
                                try:
                                    if lower_bound is not None and value_numeric < lower_bound: is_abnormal_flag = True
                                    elif upper_bound is not None and value_numeric > upper_bound: is_abnormal_flag = True
                                    elif lower_bound is not None and upper_bound is not None: is_abnormal_flag = False
                                    task_logger.debug(f"    Abnormality check by range: Value={value_numeric}, Abnormal={is_abnormal_flag}")
                                except TypeError as comp_err:
                                    task_logger.warning(f"    Could not compare value {value_numeric} with range bounds: {comp_err}")
                                except Exception as range_check_err:
                                     task_logger.error(f"    Error during range abnormality check: {range_check_err}")

                            # --- Создание Объекта TestResult ---
                            try:
                                result = TestResult.objects.create(
                                    submission=submission, analyte=analyte,
                                    value=value_str[:100], value_numeric=value_numeric,
                                    unit=(unit_str[:50] if unit_str else analyte.unit),
                                    reference_range=(ref_range_str[:150] if ref_range_str else None),
                                    status_text=(status_text_from_pdf[:100] if status_text_from_pdf else None), # <-- Сохраняем текст
                                    is_abnormal=is_abnormal_flag, # Сохраняем True/False/None
                                    extracted_at=timezone.now()
                                )
                                created_results_list.append(result)
                                parsed_results_count += 1
                                processed_analytes_in_submission.add(analyte.id)
                                found_analyte_ids_for_typing.append(analyte.id)
                                details = f"Parsed {analyte.name} ('{matched_alias}'): {value_str} {unit_str or ''}"
                                if ref_range_str: details += f" (Ref: {ref_range_str})"
                                # Используем текстовый статус в логе, если он есть
                                if status_text_from_pdf:
                                     details += f" (Status: {status_text_from_pdf})"
                                elif is_abnormal_flag is not None:
                                     details += f" (Abnormal: {is_abnormal_flag})"
                                parsing_details.append(details)
                                task_logger.info(f"[PDF Task {task_id}] Created result for {analyte.name} (ID: {result.id})")
                            except OperationalError as db_op_err:
                                task_logger.error(f"DB operational error saving result for {analyte.name}: {db_op_err}")
                                parsing_details.append(f"DB error saving result for {analyte.name}.")
                            except Exception as db_err:
                                 task_logger.exception(f"Error saving result for {analyte.name}: {db_err}", exc_info=True)
                                 parsing_details.append(f"Error saving result for {analyte.name}.")

                        except InvalidOperation:
                             task_logger.warning(f"Value '{value_str}' not valid Decimal for {analyte.name} on line {i}.")
                             parsing_details.append(f"Invalid number '{value_str}' for {analyte.name}.")
                    else:
                         task_logger.debug(f"  No numeric value found after alias '{matched_alias}' for {analyte.name} on line {i}.")

            # --- Цикл для поиска неопознанных строк ---
            task_logger.info(f"[PDF Task {task_id}] Checking for potentially unrecognized results...")
            unrecognized_count = 0
            for i, line in enumerate(lines):
                line = line.strip()
                if not line or line == '<-- Page Break -->' or i in processed_line_indices: continue
                if len(line.split()) < 3 or re.match(r'^(Показатель|Результат|Норма|Ед\. изм\.|Статус|ГЕМАТОЛОГИЯ|Биохимия|Коагулограмма|Анализ мочи)', line, re.IGNORECASE): continue
                potential_match = POTENTIAL_RESULT_PATTERN_COMPILED.search(line)
                if potential_match:
                    potential_name = potential_match.group(1).strip()
                    if len(potential_name) > 3 and re.search(r'[а-яА-ЯёЁa-zA-Z]', potential_name):
                        log_message = f"Возможно, неопознанный результат (строка {i}): '{line}'"
                        parsing_details.append(log_message)
                        task_logger.warning(log_message)
                        unrecognized_count += 1
            if unrecognized_count > 0:
                parsing_details.insert(0, f"Обнаружено {unrecognized_count} строк, похожих на неопознанные результаты (см. ниже).")
            # --- Конец цикла для неопознанных ---

        # --- Определение Типа Теста ---
        determined_type = None
        if not submission.test_type:
            determined_type = determine_test_type(found_analyte_ids_for_typing)
            if determined_type:
                parsing_details.append(f"Automatically determined Test Type: {determined_type.name}")
            else:
                 parsing_details.append("Could not automatically determine Test Type.")
        else:
             parsing_details.append(f"Test Type was pre-selected by user: {submission.test_type.name}")

        # --- Финальный Статус: Успех ---
        submission.processing_status = MedicalTestSubmission.StatusChoices.COMPLETED
        final_details = f"PDF processed ({page_count} pages). Parsed {parsed_results_count} results.\n---\n" + "\n".join(parsing_details)
        max_len = MedicalTestSubmission._meta.get_field('processing_details').max_length or 4000
        submission.processing_details = final_details[:max_len]
        processing_error = None

    except Exception as exc:
        task_logger.exception(f"[PDF Task {task_id}] Unhandled error during processing {submission_id}: {exc}", exc_info=True)
        if not processing_error:
            processing_error = f"Unexpected Processing Error: {str(exc)[:500]}"

    finally:
        if submission:
            final_status = MedicalTestSubmission.StatusChoices.FAILED if processing_error else MedicalTestSubmission.StatusChoices.COMPLETED
            details_to_save = processing_error if processing_error else submission.processing_details
            try:
                update_fields = {
                    'processing_status': final_status,
                    'processing_details': details_to_save,
                    'updated_at': timezone.now()
                }
                if determined_type and final_status == MedicalTestSubmission.StatusChoices.COMPLETED:
                     update_fields['test_type'] = determined_type
                if extracted_date and final_status == MedicalTestSubmission.StatusChoices.COMPLETED:
                     update_fields['test_date'] = extracted_date

                final_update_count = MedicalTestSubmission.objects.filter(
                    id=submission_id,
                    processing_status=MedicalTestSubmission.StatusChoices.PROCESSING
                ).update(**update_fields)

                if final_update_count > 0: task_logger.info(f"[PDF Task {task_id}] Marked submission {submission_id} as {final_status}.")
                else: task_logger.warning(f"[PDF Task {task_id}] Submission {submission_id} status not PROCESSING during final update.")
            except OperationalError as final_db_err:
                task_logger.error(f"DB error during final status update for {submission_id}: {final_db_err}")
            except Exception as final_save_err:
                task_logger.exception(f"Critical error during final status update for {submission_id}: {final_save_err}", exc_info=True)

    task_logger.info(f"[PDF Task {task_id}] Finished processing task for submission: {submission_id}")

