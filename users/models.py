from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    is_student = models.BooleanField(default=False)
    is_teacher = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    enrolled_courses = models.ManyToManyField(
        'courses.Course',
        related_name='enrolled_students',
        blank=True,
        verbose_name="Записанные курсы")

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
    
    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.is_admin = True
        super().save(*args, **kwargs)

    def is_teacher_or_admin(self):
        return self.role in ['teacher', 'admin']