from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from courses.models import Course  # подключаем модель из приложения courses
from django.contrib.auth import logout
from django.shortcuts import redirect
@login_required
def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    if request.user.is_student:
        if not course.is_active:
            raise PermissionDenied("Курс не доступен")
        # Можно добавить еще условия доступа, если нужно

    return render(request, 'courses/course_detail.html', {'course': course})

def custom_logout(request):
    logout(request)
    return redirect('/')