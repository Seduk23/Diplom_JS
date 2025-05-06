from django.utils import timezone
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from functools import wraps
from django.db.models import Avg, Max, Min
from .models import Course, Lesson, Test, Question, Answer, TestResult, Enrollment, Progress
from .forms import (
    CourseForm, LessonForm, TestForm, QuestionForm, AnswerForm,
    StudentSignUpForm, TeacherSignUpForm, TestSubmissionForm
)
from .decorators import teacher_required, student_required

def check_course_access(user, course):
    """Проверяет, имеет ли пользователь доступ к курсу."""
    if not course.can_view(user):
        raise HttpResponseForbidden(_("You do not have access to this course"))

def check_lesson_access(user, lesson):
    """Проверяет, имеет ли пользователь доступ к уроку и его публикацию."""
    if not lesson.is_published and not (user.is_staff or user.is_admin):
        raise HttpResponseForbidden(_("Lesson is not published"))
    check_course_access(user, lesson.course)

def home(request):
    """Отображает главную страницу с активными курсами."""
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
def student_dashboard(request):
    """Отображает панель студента с курсами и прогрессом."""
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
    progress = {
        enrollment.course.id: {
            'completed': Progress.objects.filter(
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

    test_results = {
        enrollment.course.id: TestResult.objects.filter(
            student=request.user,
            lesson__course=enrollment.course
        ).values('lesson__title', 'score', 'attempts')
        for enrollment in enrollments
    }

    return render(request, 'users/student_dashboard.html', {
        'enrollments': enrollments,
        'progress': progress,
        'test_results': test_results
    })

@login_required
def admin_dashboard(request):
    """Отображает панель администратора."""
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
    """Отображает панель преподавателя с курсами и результатами тестов."""
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
        context['title'] = _("Create New Course")
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
    """Управление уроками курса."""
    course = get_object_or_404(Course, id=course_id, creator=request.user)
    if request.method == 'POST':
        lesson_form = LessonForm(request.POST, request.FILES)
        if lesson_form.is_valid():
            lesson = lesson_form.save(commit=False)
            lesson.course = course
            lesson.save()
            messages.success(request, _("Lesson added successfully!"))
            return redirect('courses:manage_lessons', course_id=course.id)
    else:
        lesson_form = LessonForm()

    lessons = course.lessons.all().order_by('order')
    return render(request, 'courses/manage_lessons.html', {
        'course': course,
        'lessons': lessons,
        'lesson_form': lesson_form
    })

@login_required
def delete_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    
    # Проверка прав
    if request.user != course.creator and not request.user.is_superuser:
        messages.error(request, "У вас нет прав для удаления этого курса.")
        return redirect('courses:teacher_dashboard')
    
    if request.method == 'POST':
        try:
            # Удаление связанных объектов
            Test.objects.filter(lesson__course=course).delete()
            Lesson.objects.filter(course=course).delete()
            Enrollment.objects.filter(course=course).delete()
            Progress.objects.filter(lesson__course=course).delete()
            TestResult.objects.filter(lesson__course=course).delete()
            course.delete()
            messages.success(request, f"Курс '{course.title}' успешно удалён.")
        except Exception as e:
            messages.error(request, f"Ошибка при удалении курса: {str(e)}")
        return redirect('courses:teacher_dashboard')
    
    return redirect('courses:teacher_dashboard')

@login_required
@teacher_required
def reorder_lessons(request, course_id):
    """Переупорядочивание уроков."""
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
    """Создание теста для урока."""
    lesson = get_object_or_404(Lesson, id=lesson_id, course__creator=request.user)
    if request.method == 'POST':
        form = TestForm(request.POST)
        if form.is_valid():
            test = form.save(commit=False)
            test.lesson = lesson
            test.save()
            messages.success(request, _("Test added successfully!"))
            return redirect('courses:manage_test_questions', test_id=test.id)
    else:
        form = TestForm()
    return render(request, 'courses/create_test.html', {'form': form, 'lesson': lesson})

@login_required
@teacher_required
def manage_test_questions(request, test_id):
    """Управление вопросами теста."""
    test = get_object_or_404(Test, id=test_id, lesson__course__creator=request.user)
    if request.method == 'POST':
        question_form = QuestionForm(request.POST)
        if question_form.is_valid():
            question = question_form.save(commit=False)
            question.test = test
            question.save()
            messages.success(request, _("Question added!"))
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
    """Добавление вопроса и ответов к тесту."""
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
            messages.success(request, _("Question and answers added!"))
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
            messages.success(request, _("Question and answers updated!"))
            return redirect('courses:manage_test_questions', test_id=self.object.test.id)
        return self.render_to_response(self.get_context_data(form=question_form, answer_forms=answer_forms))

@method_decorator([login_required, teacher_required], name='dispatch')
class QuestionDeleteView(DeleteView):
    model = Question
    template_name = 'courses/delete_question.html'

    def get_queryset(self):
        return Question.objects.filter(test__lesson__course__creator=self.request.user)

    def get_success_url(self):
        messages.success(self.request, _("Question deleted!"))
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
        messages.success(self.request, _("Answer added!"))
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
        messages.success(self.request, _("Answer updated!"))
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
        messages.success(self.request, _("Answer deleted!"))
        return reverse_lazy('courses:edit_question', kwargs={'pk': self.object.question.id})

@login_required
def course_detail(request, course_id):
    """Отображает детали курса."""
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
    """Запись студента на курс."""
    course = get_object_or_404(Course, id=course_id, is_active=True)
    Enrollment.objects.get_or_create(student=request.user, course=course)
    messages.success(request, _(f"You are enrolled in {course.title}"))
    return redirect('courses:course_detail', course_id=course.id)

@login_required
@student_required
def unenroll_course(request, course_id):
    """Отмена записи студента с курса."""
    course = get_object_or_404(Course, id=course_id)
    Enrollment.objects.filter(student=request.user, course=course).delete()
    messages.success(request, _(f"You have unenrolled from {course.title}"))
    return redirect('courses:student_dashboard')

@method_decorator(login_required, name='dispatch')
class LessonDetailView(LoginRequiredMixin, DetailView):
    model = Lesson
    template_name = "courses/lesson_detail.html"
    context_object_name = "lesson"
    pk_url_kwarg = "lesson_id"

    def get_object(self, queryset=None):
        lesson = get_object_or_404(Lesson, id=self.kwargs['lesson_id'])
        check_lesson_access(self.request.user, lesson)
        return lesson

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lesson = self.object
        course = lesson.course
        lessons = course.lessons.filter(is_published=True).order_by("id")
        context["prev_lesson"] = lessons.filter(id__lt=lesson.id).last()
        context["next_lesson"] = lessons.filter(id__gt=lesson.id).first()

        # Проверяем наличие теста
        test = Test.objects.filter(lesson=lesson).first()
        context["has_test"] = bool(test)
        context["tests"] = [test] if test else []
        context["has_questions"] = test.questions.exists() if test else False

        # Проверяем прогресс студента
        context["can_access_next_lesson"] = True
        if self.request.user.is_student and context["has_test"]:
            progress = Progress.objects.filter(
                student=self.request.user, lesson=lesson, completed=True
            ).exists()
            context["can_access_next_lesson"] = progress

        # Форма теста для студентов
        if self.request.user.is_student and context["has_test"] and context["has_questions"]:
            attempt_number = TestResult.objects.filter(
                student=self.request.user, lesson=lesson
            ).count() + 1
            if attempt_number > settings.MAX_TEST_ATTEMPTS:
                messages.error(
                    self.request,
                    _("You have exceeded the maximum number of attempts for this test.")
                )
                context["form"] = None
            else:
                context["form"] = TestSubmissionForm(test=test)
                context["attempt_number"] = attempt_number
        else:
            context["form"] = None
            if self.request.user.is_student and context["has_test"] and not context["has_questions"]:
                messages.warning(
                    self.request,
                    _("This test has no questions yet. Please contact your teacher.")
                )

        # Отладочная информация
        context["debug"] = {
            "is_student": self.request.user.is_student,
            "has_test": context["has_test"],
            "test_exists": Test.objects.filter(lesson=lesson).exists(),
            "test_count": Test.objects.filter(lesson=lesson).count(),
            "test_title": test.title if test else "No test",
            "has_questions": context["has_questions"],
            "question_count": test.questions.count() if test else 0,
            "progress_completed": Progress.objects.filter(
                student=self.request.user, lesson=lesson, completed=True
            ).exists(),
            "progress_count": Progress.objects.filter(
                student=self.request.user, lesson=lesson
            ).count(),
            "form_errors": None,
            "post_data": None
        }

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()  # Загружаем объект урока
        lesson = self.object
        test = Test.objects.filter(lesson=lesson).first()

        if not request.user.is_student or not test or not test.questions.exists():
            messages.error(request, _("No test or questions available for this lesson."))
            return redirect("courses:lesson_detail", lesson_id=lesson.id)

        attempt_number = TestResult.objects.filter(
            student=request.user, lesson=lesson
        ).count() + 1

        if attempt_number > settings.MAX_TEST_ATTEMPTS:
            messages.error(
                request,
                _("You have exceeded the maximum number of attempts for this test.")
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
                    Progress.objects.update_or_create(
                        student=request.user,
                        lesson=lesson,
                        defaults={'completed': True, 'completed_at': timezone.now()}
                    )
                    messages.success(request, _("Test passed! You can now proceed to the next lesson."))
                else:
                    messages.warning(request, _("Test submitted, but you did not pass. Try again."))
                return redirect("courses:test_result", lesson_id=lesson.id)
            except Exception as e:
                messages.error(request, _(f"Error processing test: {str(e)}"))
                context["debug"]["form_errors"] = str(e)
        else:
            messages.error(request, _("Invalid test submission."))
            context["debug"]["form_errors"] = form.errors.as_json()

        context["form"] = form
        return self.render_to_response(context)

@login_required
@student_required
def test_result(request, lesson_id):
    """Отображает результаты теста для студента."""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    check_lesson_access(request.user, lesson)
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

def process_test_answers(test, request):
    """Обрабатывает ответы на тест и возвращает баллы и словарь ответов."""
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

def update_test_result(result, score, total_points, answers, test, lesson, request):
    """Обновляет или создаёт результат теста."""
    percentage = (score / total_points * 100) if total_points else 0
    if result:
        result.score = percentage
        result.answers = answers
        result.attempts += 1
        result.save()
    else:
        result = TestResult.objects.create(
            student=request.user,
            lesson=lesson,
            score=percentage,
            answers=answers,
            attempts=1
        )
    if result.score >= test.passing_score:
        Progress.objects.update_or_create(
            student=request.user,
            lesson=lesson,
            defaults={'completed': True, 'completed_at': timezone.now()}
        )
    return percentage