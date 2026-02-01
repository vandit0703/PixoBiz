import base64
from rest_framework import serializers
from django.contrib.auth.models import User
from filemanager.models import (
    Folder,
    UserFile,
    FaceEmbedding,
    Announcement,
    CalendarEvent,
    Applicant,
    Profile,
)

# =========================
# USER
# =========================
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


# =========================
# PROFILE
# =========================
class ProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Profile
        fields = [
            "id",
            "user",
            "bio",
            "phone",
            "company",
            "portfolio_url",
            "seller_status",
            "seller_message",
        ]


# =========================
# FOLDER
# =========================
class FolderSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.id")

    class Meta:
        model = Folder
        fields = ["id", "name", "parent", "user", "created_at"]


# =========================
# USER FILE
# =========================
class UserFileSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.id")

    class Meta:
        model = UserFile
        fields = [
            "id",
            "user",
            "folder",
            "file",
            "original_name",
            "file_type",
            "uploaded_at",
        ]


# =========================
# FACE EMBEDDING
# =========================
class FaceEmbeddingSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.id")
    embedding = serializers.SerializerMethodField()

    class Meta:
        model = FaceEmbedding
        fields = ["id", "user", "file", "embedding", "created_at"]

    def get_embedding(self, obj):
        # Binary → Base64 (safe for JSON)
        return base64.b64encode(obj.embedding).decode("utf-8")


# =========================
# ANNOUNCEMENT
# =========================
class AnnouncementSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.id")

    class Meta:
        model = Announcement
        fields = [
            "id",
            "user",
            "requirement",
            "occasion",
            "side",
            "camera_requirement",
            "time",
            "start_date",
            "end_date",
            "state",
            "city",
            "caste",
            "visibility",
            "created_at",
            "updated_at",
        ]


# =========================
# CALENDAR EVENT
# =========================
class CalendarEventSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source="created_by.id")

    class Meta:
        model = CalendarEvent
        fields = [
            "id",
            "title",
            "event_type",
            "start_date",
            "end_date",
            "remarks",
            "created_by",
            "is_active",
            "created_at",
            "updated_at",
        ]


# =========================
# APPLICANT
# =========================
class ApplicantSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.id")

    class Meta:
        model = Applicant
        fields = [
            "id",
            "announcement",
            "user",
            "status",
            "message",
            "applied_at",
            "updated_at",
        ]
