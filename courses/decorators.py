from django.http import HttpResponseForbidden
from django.utils.translation import gettext_lazy as _

def student_required(view_func):
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_student:
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden(_("Только студенты могут получить доступ к этой странице"))
    return wrapper

def teacher_required(view_func):
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_teacher:
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden(_("Только преподаватели могут получить доступ к этой странице"))
    return wrapper