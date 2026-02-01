from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from filemanager.models import (
    Folder,
    UserFile,
    FaceEmbedding,
    Announcement,
    CalendarEvent,
    Applicant,
)

from .serializers import (
    ProfileSerializer,
    FolderSerializer,
    UserFileSerializer,
    FaceEmbeddingSerializer,
    AnnouncementSerializer,
    CalendarEventSerializer,
)


# 🔹 PROFILE
class ProfileAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ProfileSerializer(request.user.profile)
        return Response(serializer.data)


# 🔹 FOLDERS
class FolderAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        folders = Folder.objects.filter(user=request.user)
        return Response(FolderSerializer(folders, many=True).data)

    def post(self, request):
        serializer = FolderSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


# 🔹 FILES
class UserFileAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        files = UserFile.objects.filter(user=request.user)
        return Response(UserFileSerializer(files, many=True).data)


# 🔹 FACE EMBEDDINGS
class FaceEmbeddingAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        faces = FaceEmbedding.objects.filter(user=request.user)
        return Response(FaceEmbeddingSerializer(faces, many=True).data)


# 🔹 ANNOUNCEMENTS
class AnnouncementAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Announcement.objects.filter(visibility="public")
        return Response(AnnouncementSerializer(qs, many=True).data)

    def post(self, request):
        serializer = AnnouncementSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


# 🔹 CALENDAR EVENTS
class CalendarEventAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        events = CalendarEvent.objects.filter(created_by=request.user)
        return Response(CalendarEventSerializer(events, many=True).data)


# 🔹 APPLY TO ANNOUNCEMENT
class ApplyAnnouncementAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, announcement_id):
        applicant, created = Applicant.objects.get_or_create(
            announcement_id=announcement_id,
            user=request.user,
        )
        return Response({
            "status": "applied" if created else "already_applied"
        })
