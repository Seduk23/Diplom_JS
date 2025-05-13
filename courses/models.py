from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings

class Course(models.Model):
    title = models.CharField(max_length=200, verbose_name=_("Заголовок"))
    description = models.TextField(verbose_name=_("Описание"))
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_courses', verbose_name=_("Создатель"))
    image = models.ImageField(upload_to='courses/', blank=True, null=True, verbose_name=_("Изображение"))
    is_active = models.BooleanField(default=True, verbose_name=_("Опубликован"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Создан"))

    class Meta:
        verbose_name = _("Курс")
        verbose_name_plural = _("Курсы")

    def __str__(self):
        return self.title

    def can_view(self, user):
        return user.is_authenticated and (user.is_student or user.is_teacher or user.is_admin or user.is_staff)

class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='lessons', verbose_name=_("Курс"))
    title = models.CharField(max_length=200, verbose_name=_("Заголовок"))
    description = models.TextField(blank=True, null=True, verbose_name=_("Описание"))
    content = models.TextField(blank=True, verbose_name=_("Материалы"))
    video_url = models.URLField(blank=True, verbose_name=_("Ссылка видео"))
    order = models.PositiveIntegerField(default=0, verbose_name=_("Выложить"))
    is_published = models.BooleanField(default=True, verbose_name=_("Опубликован"))

    class Meta:
        verbose_name = _("Урок")
        verbose_name_plural = _("Уроки")
        ordering = ['order']

    def __str__(self):
        return self.title
    
class Test(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    passing_score = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    # Другие поля

    class Meta:
        verbose_name = _("Тест")
        verbose_name_plural = _("Тесты")

    def __str__(self):
        return self.title
    def calculate_score(self, selected_answers):
        total_points = sum(q.points for q in self.questions.all())
        score = 0
        answer_index = 0  # Индекс для прохода по selected_answers

        for question in self.questions.all():
            if question.question_type == 'text':
                selected_text = selected_answers[answer_index] if answer_index < len(selected_answers) else ""
                correct_answer = question.answers.filter(is_correct=True).first()
                if correct_answer and selected_text.strip().lower() == correct_answer.text.strip().lower():
                    score += question.points
                answer_index += 1
            else:
                correct_answers = set(a.id for a in question.answers.filter(is_correct=True))
                if question.question_type == 'single':
                    selected = {selected_answers[answer_index].id} if answer_index < len(selected_answers) and isinstance(selected_answers[answer_index], Answer) else set()
                    answer_index += 1
                else:  # multiple
                    selected = {a.id for a in selected_answers[answer_index:answer_index + len(question.answers.filter(is_correct=True))] if isinstance(a, Answer)}
                    answer_index += len(question.answers.filter(is_correct=True))
                if selected == correct_answers:
                    score += question.points

        return (score / total_points * 100) if total_points else 0
class Question(models.Model):
    QUESTION_TYPES = (
        ('single', _("Single Choice")),
        ('multiple', _("Multiple Choice")),
        ('text', _("Text Answer")),
    )
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='questions', verbose_name=_("Тест"))
    text = models.TextField(verbose_name=_("Текст вопроса"))
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='single', verbose_name=_("Тип вопроса"))
    points = models.PositiveIntegerField(default=1, verbose_name=_("Баллы"))

    class Meta:
        verbose_name = _("Вопрос")
        verbose_name_plural = _("Вопросы")

    def __str__(self):
        return self.text

class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers', verbose_name=_("Вопрос"))
    text = models.TextField(verbose_name=_("Текст ответа"))
    is_correct = models.BooleanField(default=False, verbose_name=_("Правильный ответ"))
    order = models.PositiveIntegerField(default=0, verbose_name=_("Выложить"))

    class Meta:
        verbose_name = _("Ответ")
        verbose_name_plural = _("Ответы")
        ordering = ['order']

    def __str__(self):
        return self.text

class TestResult(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='test_results', verbose_name=_("Студент"))
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='test_results', verbose_name=_("Урок"))
    score = models.FloatField(verbose_name=_("Результат"))
    answers = models.JSONField(verbose_name=_("Ответы"))
    attempts = models.PositiveIntegerField(default=1, verbose_name=_("Попытки"))
    completed_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Выполнение"))

    class Meta:
        verbose_name = _("Результаты теста")
        verbose_name_plural = _("Результаты тестов")

    def __str__(self):
        return f"{self.student.username} - {self.lesson.title}"

class Enrollment(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrollments', verbose_name=_("Студент"))
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments', verbose_name=_("Курс"))
    enrolled_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Записан"))

    class Meta:
        verbose_name = _("Записан")
        verbose_name_plural = _("Записан")
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.student.username} - {self.course.title}"

class Progress(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='progress', verbose_name=_("Студент"))
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='progress', verbose_name=_("Урок"))
    completed = models.BooleanField(default=False, verbose_name=_("Выполнено"))
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Выполнено"))

    class Meta:
        verbose_name = _("Прогресс")
        verbose_name_plural = _("Прогресс")
        unique_together = ('student', 'lesson')

    def __str__(self):
        return f"{self.student.username} - {self.lesson.title}"