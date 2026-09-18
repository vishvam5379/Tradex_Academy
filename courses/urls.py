from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('dashboard/', views.dashboard_home, name='dashboard'),
    path('community/', views.community_view, name='community'),
    path('category/<slug:category_slug>/<slug:subcategory_slug>/', views.category_video_list, name='category_videos'),
    path('category/<slug:category_slug>/<slug:subcategory_slug>/<int:video_id>/', views.video_player, name='video_player'),
    path('api/video/<int:video_id>/complete/', views.mark_video_complete_api, name='mark_video_complete'),
    path('api/community/channel/<slug:channel_slug>/messages/', views.api_get_community_messages, name='api_get_community_messages'),
    path('api/community/channel/<slug:channel_slug>/send/', views.api_send_community_message, name='api_send_community_message'),
    path('api/community/message/<int:message_id>/delete/', views.api_delete_community_message, name='api_delete_community_message'),
]
