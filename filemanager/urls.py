# filemanager/urls.py
from django.urls import path

from faceapp import views
from .views import (
    album_face_search_view,
    bulk_delete_files,
    delete_file,
    my_applications,
    photo_album_set_pin,
    public_album_detail,
    public_album_file_download,
    rename_file,
    share_folder,
    public_album_download,
    shared_file_download,
    shared_folder_download,
    shared_folder_view,
    toggle_album_download,
    toggle_album_download,
    upload_files,
    search_selfie,
    download_search_matches,
    face_search_page,
    home_page,
    dashboard,
    announcements_list,
    announcement_create,
    calendar_view,
    calendar_events_list,
    calendar_event_create,
    calendar_event_detail,
    calendar_event_update,
    calendar_event_delete,
    apply_announcement,
    view_applicants,
    update_applicant_status,
    profile,
    user_logout,
    login_view,
    signup_view,
    profile_edit,
    change_password,
    seller_request,
    portfolio_edit,
    file_manager,
    upload_files,
    photo_album_list,
    photo_album_detail,
    create_photo_album,
    create_folder,
    rename_folder,
    delete_folder,
    photo_album_delete,
    photo_album_edit,
    album_customers,
    photo_album_verify_pin,
    upload_init,
    upload_chunk,
    paste_files,
    apply_album_watermark,
)

urlpatterns = [
    # Public home page
    path("", home_page, name="home"),
    # Dashboard (authenticated users)
    path("dashboard/", dashboard, name="dashboard"),
    path("login/", login_view, name="login"),
    path("signup/", signup_view, name="signup"),
    path("files/", file_manager, name="file_manager"),
    path("files/folder/<int:folder_id>/", file_manager, name="open_folder"),
    path("files/upload/", upload_files, name="upload_files"),
    path("files/rename/<int:file_id>/", rename_file, name="rename_file"),
    path("files/delete/<int:file_id>/", delete_file, name="delete_file"),
    path("photo-albums/", photo_album_list, name="photo_album_list"),
    path(
        "photo-albums/<int:album_id>/",
        photo_album_detail,
        name="photo_album_detail"
    ),
    path("albums/<int:album_id>/<int:folder_id>/",photo_album_detail, name="photo_album_folder"),
    path(
        "folders/<int:folder_id>/share/photo-album/",
        create_photo_album,
        name="create_photo_album"
    ),
    # Edit album
    path(
        "photo-albums/<int:album_id>/edit/",
        photo_album_edit,
        name="photo_album_edit"
    ),
    path(
        "photo-albums/<int:album_id>/toggle-download/",
        toggle_album_download,
        name="toggle_album_download"
    ),
    # Set / update PIN
    path(
        "photo-albums/<int:album_id>/set-pin/",
        photo_album_set_pin,
        name="photo_album_pin"
    ),
    path(
        "share/<uuid:share_token>/album/download/",
        public_album_download,
        name="shared_album_download"
    ),
    path(
        "share/<uuid:share_token>/album/file/<int:file_id>/download/",
        public_album_file_download,
        name="public_album_file_download"
    ),
    path(
        "album/<uuid:token>/view/",
        public_album_detail,
        name="public_album_detail"
    ),
    path(
        "album/<uuid:token>/verify-pin/",
        photo_album_verify_pin,
        name="photo_album_verify_pin"
    ),
    # Delete album
    path(
        "photo-albums/<int:album_id>/delete/",
        photo_album_delete,
        name="photo_album_delete"
    ),
    path(
        "album/<uuid:token>/",
        album_face_search_view,
        name="album_face_search"
    ),
    path(
        "albums/<int:album_id>/customers/",
        album_customers,
        name="album_customers"
    ),
    path(
        "folders/<int:folder_id>/share/",
        share_folder,
        name="share_folder"
    ),
    path("files/paste/",paste_files, name="paste_files"),
    # PUBLIC VIEW
    path(
        "shared/folder/<uuid:token>/",
        shared_folder_view,
        name="shared_folder"
    ),
    path("shared/folder/<str:token>/<int:folder_id>/", shared_folder_view, name="shared_folder_open"),
    # SECURE DOWNLOAD
    path(
        "shared/file/<uuid:token>/<int:file_id>/download/",
        shared_file_download,
        name="shared_file_download"
    ),
    path("files/bulk-delete/", bulk_delete_files, name="bulk_delete_files"),
    path(
        "shared/folder/<uuid:token>/download/",
        shared_folder_download,
        name="shared_folder_download"
    ),
    path(
        "photo-albums/<int:album_id>/apply-watermark/",
        apply_album_watermark,
        name="apply_album_watermark"
    ),
    path("folders/create/", create_folder, name="create_folder"),
    path("folders/<int:folder_id>/rename/", rename_folder, name="rename_folder"),
    path("folders/<int:folder_id>/delete/", delete_folder, name="delete_folder"),
    # Chunked upload endpoints
    path("upload/init/", upload_init, name="upload_init"),
    path("upload/chunk/", upload_chunk, name="upload_chunk"),
    path("face-search/", face_search_page, name="face_search_page"),
    path("search-selfie/", search_selfie, name="search_selfie"),
    path("search-selfie/download/", download_search_matches, name="download_search_matches"),
    path("announcements/", announcements_list, name="announcements_list"),
    path("announcements/create/", announcement_create, name="announcement_create"),
    path("announcements/apply/", apply_announcement, name="apply_announcement"),
    path("announcements/applicants/", view_applicants, name="view_applicants"),
    path("announcements/applicants/update/", update_applicant_status, name="update_applicant_status"),
    path('my-applications/', my_applications, name='my_applications'),
    path("calendar-events/", calendar_view, name="calendar_view"),
    path("calendar/", calendar_events_list, name="calendar_events_list"),
    path("calendar/create/", calendar_event_create, name="calendar_event_create"),
    path("calendar/<int:pk>/", calendar_event_detail, name="calendar_event_detail"),
    path("calendar/<int:pk>/edit/", calendar_event_update, name="calendar_event_update"),
    path("calendar/<int:pk>/delete/", calendar_event_delete, name="calendar_event_delete"),
    path("profile/", profile, name="profile"),
    path("profile/edit/", profile_edit, name="profile_edit"),
    path("profile/change-password/", change_password, name="change_password"),
    path("profile/seller-request/", seller_request, name="seller_request"),
    path("profile/portfolio/", portfolio_edit, name="portfolio_edit"),
    path("logout/", user_logout, name="logout"),
]
