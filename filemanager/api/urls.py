from django.urls import path
from .views import (
    ProfileAPI,
    FolderAPI,
    UserFileAPI,
    FaceEmbeddingAPI,
    AnnouncementAPI,
    CalendarEventAPI,
    ApplyAnnouncementAPI,
)

urlpatterns = [
    path("profile/", ProfileAPI.as_view()),
    path("folders/", FolderAPI.as_view()),
    path("files/", UserFileAPI.as_view()),
    path("faces/", FaceEmbeddingAPI.as_view()),
    path("announcements/", AnnouncementAPI.as_view()),
    path("calendar/", CalendarEventAPI.as_view()),
    path("apply/<int:announcement_id>/", ApplyAnnouncementAPI.as_view()),
]
