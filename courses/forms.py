from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Course, Lesson, Test, Question, Answer
from django.contrib.auth import get_user_model

User = get_user_model()

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['title', 'description', 'image', 'is_active']
        labels = {
            'title': _("Заголовок"),
            'description': _("Описание"),
            'image': _("Изображение"),
            'is_active': _("Опубликован"),
        }

class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ['title', 'description', 'content', 'video_url', 'is_published']
        labels = {
            'title': _("Заголовок"),
            'description': _("Описание"),
            'content': _("Материалы"),
            'video_url': _("Ссылка на видео"),
            'is_published': _("Опубликован"),
        }

class TestForm(forms.ModelForm):
    class Meta:
        model = Test
        fields = ['title', 'description', 'passing_score', 'is_active']
        labels = {
            'title': _("Заголовок"),
            'description': _("Описание"),
            'passing_score': _("Минимальный балл"),
            'is_active': _("Опубликован"),
        }

class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'question_type', 'points']
        labels = {
            'text': _("Question Text"),
            'question_type': _("Question Type"),
            'points': _("Points"),
        }

class AnswerForm(forms.ModelForm):
    class Meta:
        model = Answer
        fields = ['text', 'is_correct']
        labels = {
            'text': _("Answer Text"),
            'is_correct': _("Is Correct"),
        }

class StudentSignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label=_("Password"))

    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        labels = {
            'username': _("Имя пользователя"),
            'email': _("Email"),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.is_student = True
        if commit:
            user.save()
        return user

class TeacherSignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label=_("Password"))

    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        labels = {
            'username': _("Имя пользователя"),
            'email': _("Email"),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.is_teacher = True
        if commit:
            user.save()
        return user

class TestSubmissionForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.test = kwargs.pop('test')
        super().__init__(*args, **kwargs)
        for question in self.test.questions.all():
            field_name = f'question_{question.id}'
            if question.question_type == 'single':
                choices = [(answer.id, answer.text) for answer in question.answers.all()]
                self.fields[field_name] = forms.ChoiceField(
                    label=question.text,
                    choices=choices,
                    widget=forms.RadioSelect,
                    required=True
                )
            elif question.question_type == 'multiple':
                choices = [(answer.id, answer.text) for answer in question.answers.all()]
                self.fields[field_name] = forms.MultipleChoiceField(
                    label=question.text,
                    choices=choices,
                    widget=forms.CheckboxSelectMultiple,
                    required=True
                )
            elif question.question_type == 'text':
                self.fields[field_name] = forms.CharField(
                    label=question.text,
                    widget=forms.TextInput,
                    required=True
                )

    def clean(self):
        cleaned_data = super().clean()
        answers = []
        for question in self.test.questions.all():
            field_name = f'question_{question.id}'
            value = cleaned_data.get(field_name)
            if value:
                if question.question_type == 'single':
                    try:
                        answer = Answer.objects.get(id=value, question=question)
                        answers.append(answer)
                    except Answer.DoesNotExist:
                        self.add_error(field_name, _("Invalid answer selected."))
                elif question.question_type == 'multiple':
                    try:
                        selected_ids = [int(v) for v in value]
                        selected_answers = Answer.objects.filter(id__in=selected_ids, question=question)
                        if len(selected_answers) != len(selected_ids):
                            self.add_error(field_name, _("Invalid answers selected."))
                        answers.extend(selected_answers)
                    except (ValueError, Answer.DoesNotExist):
                        self.add_error(field_name, _("Invalid answers selected."))
                elif question.question_type == 'text':
                    answers.append(value)  # Текстовый ответ сохраняется как строка
        cleaned_data['answers'] = answers
        return cleaned_data