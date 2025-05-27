from django import template
from django.urls import reverse
from django.db.models import Count, Q
from ..models import StudentProgress, Lesson

register = template.Library()

@register.filter
def add_button(buttons, args):
    if not buttons:
        buttons = []

    if isinstance(args, str):
        try:
            # Разделяем строку на url_name, style, label
            url_name, style, label = args.split(',')
            # Предполагаем, что course_id передаётся через контекст или извлекается из предыдущей кнопки
            course_id = buttons[-1]['course_id'] if buttons and 'course_id' in buttons[-1] else None
            # Генерируем URL только если url_name и course_id определены
            base_url = reverse(url_name, kwargs={'course_id': course_id}) if url_name and course_id else ''
            full_url = base_url if course_id else url_name  # Если course_id отсутствует, используем url_name как есть
            button = {
                'url': full_url,
                'style': style.strip(),
                'label': label.strip(),
                'course_id': course_id
            }
            return buttons + [button]
        except ValueError:
            return buttons  # Игнорируем некорректный формат
    return buttons  # Если args не строка, возвращаем исходный список

@register.filter
def dict_get(dictionary, key):
    return dictionary.get(key)

@register.filter
def add_class(field, css_class):
    return field.as_widget(attrs={"class": css_class})

@register.filter
def dict_get(dictionary, key):
    """Возвращает значение из словаря по ключу."""
    return dictionary.get(key)

@register.filter
def average_progress(course):
    """Вычисляет средний прогресс студентов по курсу в процентах."""
    total_lessons = Lesson.objects.filter(course=course).count()
    if total_lessons == 0:
        return 0
    completed_lessons = StudentProgress.objects.filter(
        lesson__course=course,
        completed=True
    ).values('lesson').distinct().count()
    return (completed_lessons / total_lessons) * 100

@register.filter
def add(value, arg):
    """Конкатенирует два значения в строку."""
    return f"{value}{arg}"

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)