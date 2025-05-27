from django import template
from django.utils.html import strip_tags
import html

register = template.Library()

@register.filter
def add(value, arg):
    return f"{value}{arg}"

register = template.Library()

@register.filter
def clean_text(value):
    # Сначала убираем HTML-теги
    text = strip_tags(value)
    # Затем преобразуем HTML-сущности (например, &nbsp;) в их текстовый эквивалент
    text = html.unescape(text)
    # Заменяем неразрывные пробелы (Unicode U+00A0) на обычные пробелы
    text = text.replace('\xa0', ' ')
    # Убираем лишние пробелы
    return ' '.join(text.split())