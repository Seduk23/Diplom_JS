from django.urls import path
from . import views
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth import views as auth_views

app_name = 'courses'

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('signup/student/', views.StudentSignUpView.as_view(), name='student_signup'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('signup/teacher/', views.TeacherSignUpView.as_view(), name='teacher_signup'),
    path('course/create/', views.CourseCreateView.as_view(), name='course_create'),
    path('course/<int:pk>/edit/', views.CourseUpdateView.as_view(), name='course_edit'),
    path('course/<int:course_id>/', views.course_detail, name='course_detail'),
    path('course/<int:course_id>/enroll/', views.enroll_course, name='enroll_course'),
    path('course/<int:course_id>/unenroll/', views.unenroll_course, name='unenroll_course'),
    path('course/<int:course_id>/manage-lessons/', views.manage_lessons, name='manage_lessons'),
    path('course/<int:course_id>/delete/', views.delete_course, name='delete_course'),
    path('course/<int:course_id>/reorder-lessons/', views.reorder_lessons, name='reorder_lessons'),
    path('lesson/<int:lesson_id>/', views.LessonDetailView.as_view(), name='lesson_detail'),
    path('lesson/<int:lesson_id>/test/create/', views.create_test, name='create_test'),
    path('test/<int:test_id>/questions/', views.manage_test_questions, name='manage_test_questions'),
    path('test/<int:test_id>/add-question/', views.add_question, name='add_question'),
    path('question/<int:pk>/edit/', views.QuestionUpdateView.as_view(), name='edit_question'),
    path('question/<int:pk>/delete/', views.QuestionDeleteView.as_view(), name='delete_question'),
    path('question/<int:question_id>/answer/add/', views.AnswerCreateView.as_view(), name='add_answer'),
    path('answer/<int:pk>/edit/', views.AnswerUpdateView.as_view(), name='edit_answer'),
    path('answer/<int:pk>/delete/', views.AnswerDeleteView.as_view(), name='delete_answer'),
    path('lesson/<int:lesson_id>/test/result/', views.test_result, name='test_result'),
    path('lesson/<int:lesson_id>/test/results/', views.test_result, name='test_results'),
]