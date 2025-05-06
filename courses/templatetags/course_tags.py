from django import template
from django.urls import reverse

register = template.Library()

@register.filter
def add_button(buttons, args):
    """Добавляет кнопку в список. Аргументы: course_id или строка с параметрами."""
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
    button = {
        'url': reverse(url_name, kwargs={'course_id': course_id}) if url_name else '',
        'style': style,
        'label': label,
        'course_id': course_id
    }
    return (buttons or []) + [button]

@register.filter
def get_item(dictionary, key):
    """Возвращает значение из словаря по ключу."""
    return dictionary.get(key)