import os
from django.utils import timezone
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages  
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models import Avg, Max, Min, Sum
from .models import Course, Lesson, Term, Test, Question, Answer, TestResult, Enrollment, StudentProgress, Achievement, UserAchievement
from .forms import (
    CourseForm, LessonForm, TestForm, QuestionForm, AnswerForm,
    StudentSignUpForm, TeacherSignUpForm, TestSubmissionForm
)
from .decorators import teacher_required, student_required

def check_course_access(user, course):
    """Проверяет, имеет ли пользователь доступ к курсу."""
    if not course.can_view(user):
        raise PermissionDenied(_("You do not have access to this course"))

def check_lesson_access(request, lesson):
    """Проверяет, имеет ли пользователь доступ к уроку и его публикацию."""
    user = request.user
    if not lesson.is_published and not (user.is_staff or user.is_admin):
        raise PermissionDenied(_("Lesson is not published"))
    check_course_access(user, lesson.course)
    if user.is_student:
        lessons = lesson.course.lessons.filter(is_published=True).order_by('id')
        lesson_index = list(lessons).index(lesson)
        if lesson_index > 0:
            prev_lesson = lessons[lesson_index - 1]
            prev_progress = StudentProgress.objects.filter(student=user, lesson=prev_lesson, completed=True).exists()
            if not prev_progress:
                test = Test.objects.filter(lesson=prev_lesson).first()
                if test:
                    messages.error(request, _("You must pass the test for the previous lesson to access this one."))
                else:
                    messages.error(request, _("You must complete the previous lesson to access this one."))
                raise PermissionDenied(_("Previous lesson not completed."))

def home(request):
    courses = Course.objects.filter(is_active=True)
    return render(request, 'courses/home.html', {'courses': courses})

class StudentSignUpView(CreateView):
    form_class = StudentSignUpForm
    template_name = 'users/signup.html'
    success_url = reverse_lazy('courses:student_dashboard')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['role'] = 'student'
        return context

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, _("Registration successful!"))
        return super().form_valid(form)

class TeacherSignUpView(CreateView):
    form_class = TeacherSignUpForm
    template_name = 'users/signup.html'
    success_url = reverse_lazy('courses:teacher_dashboard')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['role'] = 'teacher'
        return context

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, _("Registration successful! Create your first course."))
        return super().form_valid(form)

@login_required
@student_required
def student_dashboard(request):
    # Получаем подписки студента
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
    
    # Прогресс по курсам
    progress = {
        enrollment.course.id: {
            'completed': StudentProgress.objects.filter(
                student=request.user,
                lesson__course=enrollment.course,
                completed=True
            ).count(),
            'total': enrollment.course.lessons.count()
        }
        for enrollment in enrollments
    }
    for data in progress.values():
        data['percent'] = int((data['completed'] / data['total']) * 100) if data['total'] else 0

    # Результаты тестов
    test_results = {
        enrollment.course.id: TestResult.objects.filter(
            student=request.user,
            lesson__course=enrollment.course
        ).values('lesson__title', 'score', 'attempts')
        for enrollment in enrollments
    }

    # Общий прогресс студента (все уроки)
    student_progress = StudentProgress.objects.filter(student=request.user).select_related('lesson')

    # Достижения
    user_achievements = UserAchievement.objects.filter(user=request.user).select_related('achievement')

    # Аналитика
    # Средний балл за тесты
    test_stats = TestResult.objects.filter(student=request.user).aggregate(
        avg_score=Avg('score'),
        total_tests=Sum('attempts')
    )
    average_score = round(test_stats['avg_score'], 2) if test_stats['avg_score'] else 0
    total_attempts = test_stats['total_tests'] or 0

    # Данные для графика прогресса
    chart_data = {
        'labels': [enrollment.course.title for enrollment in enrollments],
        'data': [progress[enrollment.course.id]['percent'] for enrollment in enrollments]
    }

    return render(request, 'users/student_dashboard.html', {
        'enrollments': enrollments,
        'progress': progress,
        'test_results': test_results,
        'student_progress': student_progress,
        'user_achievements': user_achievements,
        'average_score': average_score,
        'total_attempts': total_attempts,
        'chart_data': chart_data
    })

@login_required
def admin_dashboard(request):
    if not (request.user.is_staff or request.user.is_admin):
        return redirect('courses:home')
    context = {
        'students': settings.AUTH_USER_MODEL.objects.filter(is_student=True),
        'teachers': settings.AUTH_USER_MODEL.objects.filter(is_teacher=True),
        'courses': Course.objects.all(),
    }
    return render(request, 'users/admin_dashboard.html', context)

@login_required
@teacher_required
def teacher_dashboard(request):
    courses = Course.objects.filter(creator=request.user, is_active=True)
    test_results = {
        course.id: TestResult.objects.filter(
            lesson__course=course
        ).select_related('student', 'lesson').values(
            'student__username', 'lesson__title', 'score', 'attempts'
        )
        for course in courses
    }
    return render(request, 'users/teacher_dashboard.html', {
        'courses': courses,
        'test_results': test_results
    })

@method_decorator([login_required, teacher_required], name='dispatch')
class CourseCreateView(CreateView):
    model = Course
    form_class = CourseForm
    template_name = 'courses/course_form.html'
    success_url = reverse_lazy('courses:teacher_dashboard')

    def form_valid(self, form):
        form.instance.creator = self.request.user
        messages.success(self.request, _("Course created successfully!"))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Создать новый курс")
        return context

@method_decorator([login_required, teacher_required], name='dispatch')
class CourseUpdateView(UpdateView):
    model = Course
    form_class = CourseForm
    template_name = 'courses/course_form.html'
    success_url = reverse_lazy('courses:teacher_dashboard')

    def get_queryset(self):
        return Course.objects.filter(creator=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, _("Course updated successfully!"))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Edit Course")
        return context

@login_required
@teacher_required
def manage_lessons(request, course_id):
    course = get_object_or_404(Course, id=course_id, creator=request.user)
    if request.method == 'POST':
        lesson_form = LessonForm(request.POST, request.FILES)
        if lesson_form.is_valid():
            lesson = lesson_form.save(commit=False)
            lesson.course = course
            lesson.save()
            messages.success(request, _("Урок добавлен!"))
            return redirect('courses:manage_lessons', course_id=course.id)
    else:
        lesson_form = LessonForm()

    lessons = course.lessons.all().order_by('order')
    lessons_with_tests = [
        {
            'lesson': lesson,
            'tests': Test.objects.filter(lesson=lesson, is_active=True).select_related('lesson')
        } for lesson in lessons
    ]
    return render(request, 'courses/manage_lessons.html', {
        'course': course,
        'lessons_with_tests': lessons_with_tests,
        'lesson_form': lesson_form
    })

@csrf_exempt  # Временно для тестирования
def upload_image(request):
    if request.method == 'POST' and request.FILES.get('upload'):
        file = request.FILES['upload']
        # Сохраняем файл в папке media/uploads
        file_path = os.path.join('uploads', file.name)
        file_path = default_storage.save(file_path, file)
        file_url = settings.MEDIA_URL + file_path
        return JsonResponse({'location': file_url})  # TinyMCE ожидает 'location'
    return JsonResponse({'error': 'Неверный запрос'}, status=400)

@login_required
@teacher_required
def delete_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    if request.user != course.creator and not request.user.is_superuser:
        messages.error(request, "У вас нет прав для удаления этого курса.")
        return redirect('courses:teacher_dashboard')
    
    if request.method == 'POST':
        try:
            Test.objects.filter(lesson__course=course).delete()
            Lesson.objects.filter(course=course).delete()
            Enrollment.objects.filter(course=course).delete()
            StudentProgress.objects.filter(lesson__course=course).delete()
            TestResult.objects.filter(lesson__course=course).delete()
            course.delete()
            messages.success(request, f"Курс '{course.title}' успешно удалён.")
        except Exception as e:
            messages.error(request, f"Ошибка при удалении курса: {str(e)}")
        return redirect('courses:teacher_dashboard')
    
    # Если запрос не POST, перенаправляем обратно (форма подтверждения теперь в шаблоне)
    return redirect('courses:teacher_dashboard')

@login_required
@teacher_required
def delete_lesson(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    course = lesson.course
    if request.user != course.creator and not request.user.is_superuser:
        messages.error(request, "У вас нет прав для удаления этого урока.")
        return redirect('courses:manage_lessons', course_id=course.id)

    if request.method == 'POST':
        try:
            # Удаляем связанные тесты и их результаты
            Test.objects.filter(lesson=lesson).delete()
            lesson.delete()
            messages.success(request, f"Урок '{lesson.title}' успешно удалён.")
        except Exception as e:
            messages.error(request, f"Ошибка при удалении урока: {str(e)}")
        return redirect('courses:manage_lessons', course_id=course.id)
    return redirect('courses:manage_lessons', course_id=course.id)

def glossary(request):
    terms = Term.objects.all()
    return render(request, 'courses/glossary.html', {'terms': terms})

@login_required
@teacher_required
def delete_test(request, test_id):
    test = get_object_or_404(Test, id=test_id)
    lesson = test.lesson
    course = lesson.course
    if request.user != course.creator and not request.user.is_superuser:
        messages.error(request, "У вас нет прав для удаления этого теста.")
        return redirect('courses:manage_lessons', course_id=course.id)

    if request.method == 'POST':
        try:
            # Удаляем все результаты теста
            TestResult.objects.filter(lesson=lesson, test_id=test_id).delete()
            test.delete()
            messages.success(request, f"Тест '{test.title}' успешно удалён.")
        except Exception as e:
            messages.error(request, f"Ошибка при удалении теста: {str(e)}")
        return redirect('courses:manage_lessons', course_id=course.id)
    return redirect('courses:manage_lessons', course_id=course.id)

@login_required
@teacher_required
def reorder_lessons(request, course_id):
    if request.method == 'POST':
        course = get_object_or_404(Course, id=course_id, creator=request.user)
        order = request.POST.getlist('order[]')
        for index, lesson_id in enumerate(order):
            Lesson.objects.filter(id=lesson_id, course=course).update(order=index)
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
@teacher_required
def create_test(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id, course__creator=request.user)
    if request.method == 'POST':
        form = TestForm(request.POST)
        if form.is_valid():
            test = form.save(commit=False)
            test.lesson = lesson
            test.save()
            messages.success(request, _("Тест успешно добавлен!"))
            return redirect('courses:manage_test_questions', test_id=test.id)
    else:
        form = TestForm()
    return render(request, 'courses/create_test.html', {'form': form, 'lesson': lesson})

@login_required
@teacher_required
def manage_test_questions(request, test_id):
    test = get_object_or_404(Test, id=test_id, lesson__course__creator=request.user)
    if request.method == 'POST':
        question_form = QuestionForm(request.POST)
        if question_form.is_valid():
            question = question_form.save(commit=False)
            question.test = test
            question.save()
            messages.success(request, _("Вопрос добавлен!"))
            return redirect('courses:manage_test_questions', test_id=test.id)
    else:
        question_form = QuestionForm()

    questions = test.questions.all()
    return render(request, 'courses/manage_test_questions.html', {
        'test': test,
        'questions': questions,
        'question_form': question_form
    })

@login_required
@teacher_required
def add_question(request, test_id):
    test = get_object_or_404(Test, id=test_id, lesson__course__creator=request.user)
    if request.method == 'POST':
        question_form = QuestionForm(request.POST)
        answer_forms = [AnswerForm(request.POST, prefix=str(i)) for i in range(4)]
        if question_form.is_valid() and all(af.is_valid() for af in answer_forms):
            question = question_form.save(commit=False)
            question.test = test
            question.save()
            for i, af in enumerate(answer_forms):
                answer = af.save(commit=False)
                answer.question = question
                answer.order = i
                answer.save()
            messages.success(request, _("Вопрос и ответ добавлен!"))
            return redirect('courses:manage_test_questions', test_id=test.id)
    else:
        question_form = QuestionForm()
        answer_forms = [AnswerForm(prefix=str(i)) for i in range(4)]
    return render(request, 'courses/add_question.html', {
        'test': test,
        'question_form': question_form,
        'answer_forms': answer_forms
    })

@method_decorator([login_required, teacher_required], name='dispatch')
class QuestionUpdateView(UpdateView):
    model = Question
    form_class = QuestionForm
    template_name = 'courses/edit_question.html'

    def get_queryset(self):
        return Question.objects.filter(test__lesson__course__creator=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['answer_forms'] = [
            AnswerForm(instance=answer, prefix=str(i))
            for i, answer in enumerate(self.object.answers.all())
        ]
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        question_form = QuestionForm(request.POST, instance=self.object)
        answer_forms = [
            AnswerForm(request.POST, instance=answer, prefix=str(i))
            for i, answer in enumerate(self.object.answers.all())
        ]
        if question_form.is_valid() and all(af.is_valid() for af in answer_forms):
            question_form.save()
            for af in answer_forms:
                af.save()
            messages.success(request, _("Вопрос и ответы обновлены!"))
            return redirect('courses:manage_test_questions', test_id=self.object.test.id)
        return self.render_to_response(self.get_context_data(form=question_form, answer_forms=answer_forms))

@method_decorator([login_required, teacher_required], name='dispatch')
class QuestionDeleteView(DeleteView):
    model = Question
    template_name = 'courses/delete_question.html'

    def get_queryset(self):
        return Question.objects.filter(test__lesson__course__creator=self.request.user)

    def get_success_url(self):
        messages.success(self.request, _("Вопрос удален!"))
        return reverse_lazy('courses:manage_test_questions', kwargs={'test_id': self.object.test.id})

@method_decorator([login_required, teacher_required], name='dispatch')
class AnswerCreateView(CreateView):
    model = Answer
    form_class = AnswerForm
    template_name = 'courses/add_answer.html'

    def form_valid(self, form):
        question = get_object_or_404(
            Question,
            id=self.kwargs['question_id'],
            test__lesson__course__creator=self.request.user
        )
        form.instance.question = question
        messages.success(self.request, _("Ответ добавлен!"))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('courses:edit_question', kwargs={'pk': self.kwargs['question_id']})

@method_decorator([login_required, teacher_required], name='dispatch')
class AnswerUpdateView(UpdateView):
    model = Answer
    form_class = AnswerForm
    template_name = 'courses/edit_answer.html'

    def get_queryset(self):
        return Answer.objects.filter(question__test__lesson__course__creator=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, _("Ответ обновлен!"))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('courses:edit_question', kwargs={'pk': self.object.question.id})

@method_decorator([login_required, teacher_required], name='dispatch')
class AnswerDeleteView(DeleteView):
    model = Answer
    template_name = 'courses/delete_answer.html'

    def get_queryset(self):
        return Answer.objects.filter(question__test__lesson__course__creator=self.request.user)

    def get_success_url(self):
        messages.success(self.request, _("Ответ удален!"))
        return reverse_lazy('courses:edit_question', kwargs={'pk': self.object.question.id})

@login_required
def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    check_course_access(request.user, course)
    lessons = course.lessons.filter(is_published=True).order_by('order')
    enrolled = course.enrollments.filter(student=request.user).exists() if request.user.is_authenticated else False
    return render(request, 'courses/course_detail.html', {
        'course': course,
        'lessons': lessons,
        'enrolled': enrolled
    })

@login_required
@student_required
def enroll_course(request, course_id):
    course = get_object_or_404(Course, id=course_id, is_active=True)
    Enrollment.objects.get_or_create(student=request.user, course=course)
    messages.success(request, _(f"Вы подписаны на {course.title}"))
    return redirect('courses:course_detail', course_id=course.id)

@login_required
@student_required
def unenroll_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    Enrollment.objects.filter(student=request.user, course=course).delete()
    messages.success(request, _(f"Вы отписаны от {course.title}"))
    return redirect('courses:student_dashboard')

@method_decorator([login_required, teacher_required], name='dispatch')
class CourseUpdateView(UpdateView):
    model = Course
    form_class = CourseForm
    template_name = 'courses/course_form.html'
    success_url = reverse_lazy('courses:teacher_dashboard')

    def get_queryset(self):
        return Course.objects.filter(creator=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, _("Курс успешно обновлен!"))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Edit Course")
        return context

@method_decorator([login_required, teacher_required], name='dispatch')
class LessonUpdateView(UpdateView):
    model = Lesson
    form_class = LessonForm
    template_name = 'courses/lesson_form.html'
    success_url = reverse_lazy('courses:teacher_dashboard')

    def get_queryset(self):
        return Lesson.objects.filter(course__creator=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, _("Урок успешно обновлен!"))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("Ошибка при обновлении урока. Проверьте форму."))
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Edit Lesson")
        context['course'] = self.object.course
        return context

    def get_success_url(self):
        return reverse_lazy('courses:manage_lessons', kwargs={'course_id': self.object.course.id})

@method_decorator(login_required, name='dispatch')
class LessonDetailView(LoginRequiredMixin, DetailView):
    model = Lesson
    template_name = "courses/lesson_detail.html"
    context_object_name = "lesson"
    pk_url_kwarg = "lesson_id"

    def get_object(self, queryset=None):
        lesson = get_object_or_404(Lesson, id=self.kwargs['lesson_id'])
        check_lesson_access(self.request, lesson)
        return lesson

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lesson = self.object
        course = lesson.course
        lessons = course.lessons.filter(is_published=True).order_by("id")
        context["course"] = course
        context["prev_lesson"] = lessons.filter(id__lt=lesson.id).last()
        context["next_lesson"] = lessons.filter(id__gt=lesson.id).first()

        tests = Test.objects.filter(lesson=lesson, is_active=True)
        context["has_test"] = tests.exists()
        context["tests"] = [
            {
                'test': test,
                'has_questions': test.questions.exists(),
                'form': None,
                'attempt_number': None
            } for test in tests
        ]

        if self.request.user.is_student:
            context["last_test_result"] = TestResult.objects.filter(
                student=self.request.user, lesson=lesson
            ).order_by('-completed_at').first()

            for test_data in context["tests"]:
                test = test_data['test']
                attempt_number = TestResult.objects.filter(
                    student=self.request.user, lesson=lesson
                ).count() + 1
                if attempt_number > settings.MAX_TEST_ATTEMPTS:
                    messages.error(
                        self.request,
                        _("Вы достигли максимального количества попыток ") + test.title
                    )
                    test_data['form'] = None
                elif test_data['has_questions']:
                    test_data['form'] = TestSubmissionForm(test=test)
                    test_data['attempt_number'] = attempt_number
                else:
                    messages.warning(
                        self.request,
                        _("Тест ") + test.title + _(" Нет вопросов. Сообщите преподавателю об этом.")
                    )
                    test_data['form'] = None

            progress = StudentProgress.objects.filter(
                student=self.request.user, lesson=lesson, completed=True
            ).exists()
            context["can_access_next_lesson"] = progress
        else:
            context["can_access_next_lesson"] = True
            context["last_test_result"] = None

        context["debug"] = {
            "is_student": self.request.user.is_student,
            "has_test": context["has_test"],
            "test_count": tests.count(),
            "test_titles": [test.title for test in tests],
            "has_questions": [test.questions.exists() for test in tests],
            "question_count": [test.questions.count() for test in tests],
            "progress_completed": StudentProgress.objects.filter(
                student=self.request.user, lesson=lesson, completed=True
            ).exists(),
            "progress_count": StudentProgress.objects.filter(
                student=self.request.user, lesson=lesson
            ).count(),
            "form_errors": None,
            "post_data": None,
            "last_test_result": context["last_test_result"].score if context["last_test_result"] else None
        }

        return context

    def post(self, request, *args, **kwargs):
        from django.utils.translation import gettext_lazy as _
        self.object = self.get_object()
        lesson = self.object
        test_id = request.POST.get('test_id')
        test = get_object_or_404(Test, id=test_id, lesson=lesson)

        if not request.user.is_student or not test.questions.exists():
            messages.error(request, _("Для этого теста нет вопросов."))
            return redirect("courses:lesson_detail", lesson_id=lesson.id)

        attempt_number = TestResult.objects.filter(
            student=request.user, lesson=lesson
        ).count() + 1

        if attempt_number > settings.MAX_TEST_ATTEMPTS:
            messages.error(
                request,
                _("Вы набрали максимальное количество попыток в тесте.")
            )
            return redirect("courses:lesson_detail", lesson_id=lesson.id)

        form = TestSubmissionForm(request.POST, test=test)
        context = self.get_context_data()
        context["debug"]["post_data"] = dict(request.POST)

        if form.is_valid():
            selected_answers = form.cleaned_data.get("answers")
            try:
                score = test.calculate_score(selected_answers)
                TestResult.objects.create(
                    student=request.user,
                    lesson=lesson,
                    score=score,
                    answers=[answer.id if isinstance(answer, Answer) else answer for answer in selected_answers],
                    attempts=attempt_number,
                )
                if score >= test.passing_score:
                    StudentProgress.objects.update_or_create(
                        student=request.user,
                        lesson=lesson,
                        defaults={'completed': True, 'completed_at': timezone.now()}
                    )
                    # Проверка и награждение достижениями
                    completed_lessons = StudentProgress.objects.filter(student=request.user, completed=True).count()
                    if completed_lessons == 1:
                        achievement, _ = Achievement.objects.get_or_create(
                            name="Первый завершённый урок",
                            defaults={'description': "Завершил свой первый урок!", 'badge_image': None}
                        )
                        UserAchievement.objects.get_or_create(user=request.user, achievement=achievement)
                        messages.success(request, _("Поздравляем! Вы получили достижение 'Первый завершённый урок'!"))
                else:
                    messages.warning(request, _("Результат отправлен, но вы не набрали нужное количество баллов."))
                return redirect("courses:test_result", lesson_id=lesson.id)
            except Exception as e:
                messages.error(request, _(f"Ошибка выполнения: {str(e)}"))
                context["debug"]["form_errors"] = str(e)
        else:
            messages.error(request, _("Invalid test submission."))
            context["debug"]["form_errors"] = form.errors.as_json()

        for test_data in context["tests"]:
            if test_data['test'].id == test.id:
                test_data['form'] = form
        return self.render_to_response(context)

@login_required
@teacher_required
def lesson_preview(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id, course__creator=request.user)
    tests = Test.objects.filter(lesson=lesson, is_active=True).prefetch_related('questions__answers')
    return render(request, 'courses/lesson_preview.html', {
        'lesson': lesson,
        'tests': tests
    })

@login_required
@teacher_required
def manage_test_results(request, test_id):
    test = get_object_or_404(Test, id=test_id, lesson__course__creator=request.user)
    results = TestResult.objects.filter(lesson=test.lesson).select_related('student')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete_all':
            results.delete()
            messages.success(request, _("Все результаты тестов удалены."))
        elif action == 'delete_student':
            student_id = request.POST.get('student_id')
            results.filter(student_id=student_id).delete()
            messages.success(request, _("Результаты теста студента удалены."))
        return redirect('courses:manage_test_results', test_id=test.id)

    return render(request, 'courses/manage_test_results.html', {
        'test': test,
        'results': results
    })

@login_required
@student_required
def test_result(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    check_lesson_access(request, lesson)
    results = TestResult.objects.filter(student=request.user, lesson=lesson).order_by('-completed_at')
    stats = results.aggregate(
        avg_score=Avg('score'),
        max_score=Max('score'),
        min_score=Min('score')
    )
    return render(request, 'courses/test_results.html', {
        'lesson': lesson,
        'results': results,
        'stats': {
            'avg': stats['avg_score'] or 0,
            'max': stats['max_score'] or 0,
            'min': stats['min_score'] or 0,
        }
    })

@login_required
@student_required
def complete_lesson(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    check_lesson_access(request, lesson)
    progress, created = StudentProgress.objects.get_or_create(
        student=request.user, lesson=lesson,
        defaults={'completed': True, 'completed_at': timezone.now()}
    )
    if not created:
        progress.completed = True
        progress.completed_at = timezone.now()
        progress.save()
    
    # Проверка и награждение достижениями
    completed_lessons = StudentProgress.objects.filter(student=request.user, completed=True).count()
    if completed_lessons == 1:
        achievement, _ = Achievement.objects.get_or_create(
            name="Первый завершённый урок",
            defaults={'description': "Завершил свой первый урок!", 'badge_image': None}
        )
        UserAchievement.objects.get_or_create(user=request.user, achievement=achievement)
        messages.success(request, _("Поздравляем! Вы получили достижение 'Первый завершённый урок'!"))
    
    return redirect('courses:lesson_detail', lesson_id=lesson.id)

def process_test_answers(test, request):
    answers = {}
    score = 0
    total_points = sum(q.points for q in test.questions.all())

    for question in test.questions.all():
        key = f'question_{question.id}'
        selected = set(map(int, request.POST.getlist(key))) if question.question_type != 'text' else request.POST.get(key)
        correct = set(a.id for a in question.answers.filter(is_correct=True)) if question.question_type != 'text' else question.answers.first().text
        if question.question_type == 'text':
            if selected.strip().lower() == correct.strip().lower():
                score += question.points
            answers[str(question.id)] = selected
        else:
            if selected == correct:
                score += question.points
            answers[str(question.id)] = list(selected)

    return score, total_points, answers

def update_test_result(result, score, total_points, messages, test, lesson, request):
    percentage = (score / total_points * 100) if total_points else 0
    if result:
        result.score = percentage
        result.answers = messages
        result.attempts += 1
        result.save()
    else:
        result = TestResult.objects.create(
            student=request.user,
            lesson=lesson,
            score=percentage,
            answers=messages,
            attempts=1
        )
    if result.score >= test.passing_score:
        StudentProgress.objects.update_or_create(
            student=request.user,
            lesson=lesson,
            defaults={'completed': True, 'completed_at': timezone.now()}
        )
    return percentage