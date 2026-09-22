from django.urls import path
from . import views_admin

app_name = 'courses_admin'

urlpatterns = [
    path('', views_admin.admin_lectures_view, name='admin_lectures'),
    path('<int:lecture_id>/edit/', views_admin.admin_lecture_edit_view, name='admin_lecture_edit'),
    path('<int:lecture_id>/delete/', views_admin.admin_lecture_delete_view, name='admin_lecture_delete'),
    path('<int:lecture_id>/signed-url/', views_admin.admin_lecture_signed_url_api, name='admin_lecture_signed_url'),
]
