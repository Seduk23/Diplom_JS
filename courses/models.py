from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings

class Course(models.Model):
    title = models.CharField(max_length=200, verbose_name=_("Title"))
    description = models.TextField(verbose_name=_("Description"))
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_courses', verbose_name=_("Creator"))
    image = models.ImageField(upload_to='courses/', blank=True, null=True, verbose_name=_("Image"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))

    class Meta:
        verbose_name = _("Course")
        verbose_name_plural = _("Courses")

    def __str__(self):
        return self.title

    def can_view(self, user):
        return user.is_authenticated and (user.is_student or user.is_teacher or user.is_admin or user.is_staff)

class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='lessons', verbose_name=_("Course"))
    title = models.CharField(max_length=200, verbose_name=_("Title"))
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))
    content = models.TextField(blank=True, verbose_name=_("Content"))
    video_url = models.URLField(blank=True, verbose_name=_("Video URL"))
    order = models.PositiveIntegerField(default=0, verbose_name=_("Order"))
    is_published = models.BooleanField(default=True, verbose_name=_("Is Published"))

    class Meta:
        verbose_name = _("Lesson")
        verbose_name_plural = _("Lessons")
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
        verbose_name = _("Test")
        verbose_name_plural = _("Tests")

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
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='questions', verbose_name=_("Test"))
    text = models.TextField(verbose_name=_("Question Text"))
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='single', verbose_name=_("Question Type"))
    points = models.PositiveIntegerField(default=1, verbose_name=_("Points"))

    class Meta:
        verbose_name = _("Question")
        verbose_name_plural = _("Questions")

    def __str__(self):
        return self.text

class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers', verbose_name=_("Question"))
    text = models.TextField(verbose_name=_("Answer Text"))
    is_correct = models.BooleanField(default=False, verbose_name=_("Is Correct"))
    order = models.PositiveIntegerField(default=0, verbose_name=_("Order"))

    class Meta:
        verbose_name = _("Answer")
        verbose_name_plural = _("Answers")
        ordering = ['order']

    def __str__(self):
        return self.text

class TestResult(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='test_results', verbose_name=_("Student"))
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='test_results', verbose_name=_("Lesson"))
    score = models.FloatField(verbose_name=_("Score"))
    answers = models.JSONField(verbose_name=_("Answers"))
    attempts = models.PositiveIntegerField(default=1, verbose_name=_("Attempts"))
    completed_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Completed At"))

    class Meta:
        verbose_name = _("Test Result")
        verbose_name_plural = _("Test Results")

    def __str__(self):
        return f"{self.student.username} - {self.lesson.title}"

class Enrollment(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrollments', verbose_name=_("Student"))
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments', verbose_name=_("Course"))
    enrolled_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Enrolled At"))

    class Meta:
        verbose_name = _("Enrollment")
        verbose_name_plural = _("Enrollments")
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.student.username} - {self.course.title}"

class Progress(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='progress', verbose_name=_("Student"))
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='progress', verbose_name=_("Lesson"))
    completed = models.BooleanField(default=False, verbose_name=_("Completed"))
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Completed At"))

    class Meta:
        verbose_name = _("Progress")
        verbose_name_plural = _("Progress")
        unique_together = ('student', 'lesson')

    def __str__(self):
        return f"{self.student.username} - {self.lesson.title}"