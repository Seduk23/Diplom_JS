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
        if '|' in args:
            course_id, params = args.split('|')
            url_name, style, label = params.split(',')
        else:
            url_name, style, label = args.split(',')
            course_id = buttons[-1]['course_id'] if buttons else ''
    else:
        course_id = args
        url_name, style, label = '', '', ''

    # Формируем базовый URL без параметров
    base_url = reverse(url_name, kwargs={'course_id': course_id}) if url_name else ''
    # Добавляем query string с course_id
    full_url = f"{base_url}?course_id={course_id}" if url_name and course_id else base_url

    button = {
        'url': full_url,
        'style': style,
        'label': label,
        'course_id': course_id
    }
    return buttons + [button]

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