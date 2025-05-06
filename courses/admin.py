from django.contrib import admin
from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test

from .models import Course, Lesson, Test, Question, Answer, TestResult

User = get_user_model()


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 1


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator', 'lesson_count', 'student_count', 'is_active')
    inlines = [LessonInline]  # Добавлено для отображения уроков в курсе

    def has_add_permission(self, request):
        return getattr(request.user, 'is_teacher', False) or getattr(request.user, 'is_admin', False)

    def has_change_permission(self, request, obj=None):
        if obj:
            return obj.creator == request.user or request.user.is_superuser
        return True

    def lesson_count(self, obj):
        return obj.lessons.count()

    def student_count(self, obj):
        return obj.enrolled_students.count()  # Изменено для использования связи ManyToMany
    
    def delete_model(self, request, obj):
        try:
            # Удаляем связанные тесты через уроки
            Test.objects.filter(lesson__course=obj).delete()
            obj.delete()
        except Exception as e:
            self.message_user(request, f"Ошибка удаления: {str(e)}", level='ERROR')


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 1


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    show_change_link = True


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'is_published', 'order')
    list_filter = ('course', 'is_published')
    list_editable = ('order',)  # Добавлено для удобного изменения порядка
    search_fields = ('title', 'content')


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ('title', 'lesson', 'passing_score', 'is_active')
    inlines = [QuestionInline]
    list_filter = ('is_active', 'lesson__course')
    search_fields = ('title', 'lesson__title')


@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'lesson', 'score', 'completed_at')
    list_filter = ('lesson__course', 'student')
    search_fields = ('student__username', 'lesson__title')
    readonly_fields = ('completed_at',)  # Добавлено, чтобы дата не редактировалась


@login_required
@user_passes_test(lambda u: u.is_superuser or getattr(u, 'is_admin', False))
def admin_dashboard(request):
    courses = Course.objects.all()
    return render(request, 'courses/admin_dashboard.html', {'courses': courses})