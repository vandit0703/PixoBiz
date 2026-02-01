from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Folder, UserFile, FolderShare, FaceEmbedding, PhotoAlbum, Plan, Profile, UploadSession


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "storage_limit_gb", "price")
    search_fields = ("name",)


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    readonly_fields = ("storage_used",)


class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "storage_used")
    list_select_related = ("user", "plan")
    readonly_fields = ("storage_used",)


@admin.register(UserFile)
class UserFileAdmin(admin.ModelAdmin):
    list_display = ("id", "original_name", "user", "file_size", "uploaded_at")
    search_fields = ("original_name",)
    list_filter = ("file_type",)


admin.site.register(Folder)
admin.site.register(FolderShare)
admin.site.register(FaceEmbedding)
admin.site.register(PhotoAlbum)
admin.site.register(UploadSession)
