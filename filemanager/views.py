import base64
import zipfile
import io
import json
import time
from django.shortcuts import render
from django.http import FileResponse, HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import logout, authenticate, login
from django.contrib.auth.models import User
from django.db import IntegrityError
import json
import numpy as np
import faiss
from django.http import HttpResponse
import tempfile
import os
import calendar
import shutil
from datetime import datetime, timedelta
from urllib.parse import quote as urlquote
import requests
from .tasks import generate_thumbnail, extract_face_embeddings
from django.db.models import Q
from django.views.decorators.http import require_POST
from .models import FaceSearchLog, FolderShare, UserFile, FaceEmbedding, CalendarEvent, Applicant,PhotoAlbum, UploadSession
from .utils import extract_faces, extract_single_face
from .models import Announcement,Folder
from .forms import AnnouncementForm, CalendarEventForm, ProfileForm, SellerRequestForm
from .models import Profile
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.utils import timezone
from django.conf import settings

@login_required
def dashboard(request):
    return render(request, "filemanager/base.html")

ALLOWED_EXTENSIONS = [
    ".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff",
    ".cr2", ".cr3", ".nef", ".arw", ".dng", ".raf", ".orf", ".rw2", ".pef",
    ".mp4", ".mov", ".avi", ".mkv", ".mts", ".m2ts",
    ".psd", ".xmp", ".zip"
]
IMAGE_EXTENSIONS = [
    ".jpg", ".jpeg", ".png", ".webp",
    ".tif", ".tiff",
    ".cr2", ".cr3", ".nef", ".arw", ".dng", ".raf", ".orf", ".rw2", ".pef"
]

# Chunking threshold: files larger than this MUST be uploaded via chunked upload (10 MB)

CHUNK_SIZE = 100 * 1024 * 1024
BASE_DIR = settings.BASE_DIR
CHUNK_ROOT = os.path.join(BASE_DIR, "runtime_chunks")
os.makedirs(CHUNK_ROOT, exist_ok=True)

# =========================
# Folder recursive helper
# =========================
def get_all_subfolders(folder):
    result = []
    stack = [folder]

    while stack:
        f = stack.pop()
        children = list(Folder.objects.filter(parent=f))
        result.extend(children)
        stack.extend(children)

    return result
 
# ============================
# FILE MANAGER (GRID / LIST)
# ============================
@login_required
def file_manager(request, folder_id=None):
    user = request.user
    current_folder = None

    if folder_id:
        current_folder = get_object_or_404(
            Folder,
            id=folder_id,
            user=user
        )

    folders = Folder.objects.filter(
        user=user,
        parent=current_folder
    ).order_by("name")

    # Numeric ordering: first numeric_key (if present), then fallback to original_name
    files = UserFile.objects.filter(
        user=user,
        folder=current_folder
    ).order_by("numeric_key", "original_name")

    return render(request, "filemanager/index.html", {
        "folders": folders,
        "files": files,
        "current_folder": current_folder,
    })


# ============================
# FILE UPLOAD (AJAX / FORM)
# ============================

@login_required
def upload_files(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    user = request.user
    uploaded_count = 0

    profile = getattr(user, 'profile', None)

    for f in request.FILES.getlist("files"):
        # For large files raw upload not allowed; use chunked upload
        if f.size > CHUNK_SIZE:
            return JsonResponse({"error": "File too large. Please use the chunked upload (client will use chunks for large files)."}, status=400)

        relative_path = request.POST.get(f.name)
        parent_id = request.POST.get('parent_id')
        current_folder = None

        if parent_id:
            try:
                current_folder = Folder.objects.get(id=parent_id, user=user)
            except Folder.DoesNotExist:
                current_folder = None

        if relative_path:
            parts = relative_path.replace("\\", "/").split("/")[:-1]
            for folder_name in parts:
                current_folder, _ = Folder.objects.get_or_create(
                    user=user,
                    name=folder_name,
                    parent=current_folder
                )

        # storage check
        if profile and not profile.has_space_for(f.size):
            return JsonResponse({"error": "Storage quota exceeded. Upload blocked by plan limit."}, status=400)


        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return JsonResponse({"error": f"File type {ext} not allowed."}, status=400)

        if ext in IMAGE_EXTENSIONS:
            file_type = "image"
        elif ext in [".mp4", ".webm", ".ogg", ".mov", ".avi", ".mkv", ".mts", ".m2ts"]:
            file_type = "video"
        else:
            file_type = "file"

        user_file = UserFile.objects.create(
            user=user,
            folder=current_folder,
            file=f,
            original_name=f.name,
            file_type=file_type
        )

        uploaded_count += 1
        if file_type == "image":
            generate_thumbnail.delay(user_file.id)
            extract_face_embeddings.delay(user_file.id)
# ============================
# FILE OPEN VIEW (for all allowed types)
# ============================


@login_required
def open_file(request, file_id):
    user_file = get_object_or_404(UserFile, id=file_id, user=request.user)
    ext = os.path.splitext(user_file.original_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return HttpResponseForbidden("File type not allowed.")

    # For images and videos, show inline; for others, force download
    as_attachment = False if ext in IMAGE_EXTENSIONS or ext in [
        ".mp4", ".webm", ".ogg", ".mov", ".avi", ".mkv", ".mts", ".m2ts"
    ] else True

    response = FileResponse(user_file.file.open("rb"), as_attachment=as_attachment)
    response["Content-Disposition"] = (
        ("inline; filename=\"%s\"" % urlquote(user_file.original_name))
        if not as_attachment else
        ("attachment; filename=\"%s\"" % urlquote(user_file.original_name))
    )
    return response

    return JsonResponse({"status": "success", "uploaded": uploaded_count})

@login_required
def rename_file(request, file_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    try:
        data = json.loads(request.body)
        new_name = data.get("name")

        if not new_name:
            return JsonResponse({"error": "Empty name"}, status=400)

        user_file = UserFile.objects.get(
            id=file_id,
            user=request.user
        )

        user_file.original_name = new_name
        user_file.save()

        return JsonResponse({"success": True})

    except UserFile.DoesNotExist:
        return JsonResponse({"error": "File not found"}, status=404)

@login_required
def delete_file(request, file_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    try:
        user_file = UserFile.objects.get(
            id=file_id,
            user=request.user
        )

        # 🔴 delete physical file safely (ignore errors)
        try:
            user_file.file.delete(save=False)
        except Exception:
            pass

        # 🔴 delete DB record
        user_file.delete()

        return JsonResponse({"success": True})

    except UserFile.DoesNotExist:
        return JsonResponse({"error": "File not found"}, status=404)
    
@login_required
def rename_folder(request, folder_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    try:
        data = json.loads(request.body)
        new_name = data.get("name")

        if not new_name:
            return JsonResponse({"error": "Empty name"}, status=400)

        folder = Folder.objects.get(
            id=folder_id,
            user=request.user
        )

        folder.name = new_name
        folder.save()

        return JsonResponse({"success": True})

    except Folder.DoesNotExist:
        return JsonResponse({"error": "Folder not found"}, status=404)

@login_required
def delete_folder(request, folder_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    try:
        folder = Folder.objects.get(
            id=folder_id,
            user=request.user
        )

        # delete files inside folder
        for f in folder.files.all():
            try:
                f.file.delete(save=False)
            except Exception:
                pass
            f.delete()

        folder.delete()

        return JsonResponse({"success": True})

    except Folder.DoesNotExist:
        return JsonResponse({"error": "Folder not found"}, status=404)

# ============================
# CREATE SHARE LINK (PRIVATE)
# ============================
@login_required
@require_POST
def share_folder(request, folder_id):
    folder = get_object_or_404(
        Folder,
        id=folder_id,
        user=request.user
    )

    allow_download = request.POST.get("allow_download") == "true"

    share = FolderShare.objects.create(
        folder=folder,
        allow_download=allow_download,
        created_by=request.user
    )

    return JsonResponse({
        "success": True,
        "share_url": request.build_absolute_uri(
            f"/shared/folder/{share.token}/"
        )
    })

def public_album_download(request, share_token):
    album = get_object_or_404(PhotoAlbum, public_token=share_token)

    # 🚫 Download disabled
    if not album.allow_download:
        return HttpResponseForbidden("Download disabled")

    # 🔐 PIN protection (same as album view)
    if album.pin:
        session_key = f"album_full_access_{album.public_token}"
        if not request.session.get(session_key):
            return HttpResponseForbidden("PIN verification required")

    all_folders = [album.folder] + get_all_subfolders(album.folder)
    files = UserFile.objects.filter(folder__in=all_folders).order_by("numeric_key", "original_name")

    response = HttpResponse(content_type="application/zip")
    response["Content-Disposition"] = (
        f'attachment; filename="{album.album_name}.zip"'
    )

    with zipfile.ZipFile(response, "w", zipfile.ZIP_DEFLATED) as zipf:
        for f in files:
            if f.file and os.path.exists(f.file.path):
                zipf.write(
                    f.file.path,
                    arcname=f.original_name
                )

    return response

def public_album_file_download(request, share_token, file_id):
    album = get_object_or_404(
        PhotoAlbum,
        public_token=share_token
    )

    # 🚫 Download disabled
    if not album.allow_download:
        return HttpResponseForbidden("Download disabled")

    # 🔐 PIN protection
    if album.pin:
        session_key = f"album_full_access_{album.public_token}"
        if not request.session.get(session_key):
            return HttpResponseForbidden("PIN verification required")

    all_folders = [album.folder] + get_all_subfolders(album.folder)

    file = get_object_or_404(
        UserFile,
        id=file_id,
        folder__in=all_folders
    )

    return FileResponse(
        file.file.open("rb"),
        as_attachment=True,
        filename=file.original_name
    )


@login_required
@require_POST
def create_folder(request):
    """Create a new folder inside the currently opened folder (parent passed in POST as parent_id)"""
    user = request.user
    parent_id = request.POST.get("parent_id")
    name = request.POST.get("name")

    if not name:
        return JsonResponse({"error": "Folder name required"}, status=400)

    parent = None
    if parent_id:
        parent = get_object_or_404(Folder, id=parent_id, user=user)

    folder, created = Folder.objects.get_or_create(
        user=user,
        name=name,
        parent=parent
    )

    return JsonResponse({
        "success": True,
        "id": folder.id,
        "name": folder.name
    })


@login_required
@require_POST
def upload_init(request):
    """Start a chunked upload session. Returns upload_id."""
    user = request.user
    filename = request.POST.get("filename")
    relative_path = request.POST.get("relative_path")
    total_size = int(request.POST.get("total_size") or 0)
    total_chunks = int(request.POST.get("total_chunks") or 0)
    parent_id = request.POST.get("parent_id")
    
    if not filename or total_size <= 0 or total_chunks <= 0:
        return JsonResponse({"error": "Invalid params"}, status=400)

    # storage check
    profile = getattr(user, 'profile', None)
    if profile and not profile.has_space_for(total_size):
        return JsonResponse({"error": "Storage quota exceeded. Upload blocked by plan limit."}, status=400)

    session = UploadSession.objects.create(
        user=user,
        filename=filename,
        relative_path=relative_path,
        total_size=total_size,
        total_chunks=total_chunks,
        parent_id=parent_id,   # ✅ SAVE
    )

    return JsonResponse({"upload_id": str(session.id)})

@login_required
@require_POST
def upload_chunk(request):
    from django.db import transaction
    from django.core.files.base import File as DjangoFile

    user = request.user
    upload_id = request.POST.get("upload_id")
    chunk_index = int(request.POST.get("chunk_index", -1))
    parent_id = request.POST.get("parent_id")

    if not upload_id or chunk_index < 0 or "chunk" not in request.FILES:
        return JsonResponse({"error": "Invalid chunk data"}, status=400)

    try:
        session = UploadSession.objects.get(id=upload_id, user=user)
    except UploadSession.DoesNotExist:
        return JsonResponse({"error": "Upload session not found"}, status=404)

    # 📁 store chunks on REAL disk
    upload_dir = os.path.join(CHUNK_ROOT, str(session.id))
    os.makedirs(upload_dir, exist_ok=True)

    chunk_path = os.path.join(upload_dir, f"chunk_{chunk_index}")

    # ♻️ resume support
    if not os.path.exists(chunk_path):
        with open(chunk_path, "wb") as out:
            for data in request.FILES["chunk"].chunks():
                out.write(data)

    # 🔎 check if all chunks exist
    for i in range(session.total_chunks):
        if not os.path.exists(os.path.join(upload_dir, f"chunk_{i}")):
            return JsonResponse({"success": True})

    # 🔒 lock merge
    with transaction.atomic():
        session = UploadSession.objects.select_for_update().get(id=session.id)
        if session.completed:
            return JsonResponse({"success": True})
        session.completed = True
        session.save()

    # 🧩 assemble file (streamed)
    assembled_path = os.path.join(upload_dir, "assembled")
    with open(assembled_path, "wb") as wfd:
        for i in range(session.total_chunks):
            part_path = os.path.join(upload_dir, f"chunk_{i}")
            with open(part_path, "rb") as fd:
                shutil.copyfileobj(fd, wfd, length=1024 * 1024)

    # ✅ verify size
    if os.path.getsize(assembled_path) != session.total_size:
        return JsonResponse({"error": "Size mismatch"}, status=400)

    # 📂 create folder structure
    # 📂 build folder structure correctly
    current_folder = None

    # start from selected parent folder first
    if parent_id:
        current_folder = get_object_or_404(Folder, id=parent_id, user=user)

    # then apply nested relative path folders inside it
    if session.relative_path:
        parts = session.relative_path.replace("\\", "/").split("/")[:-1]
        for folder_name in parts:
            current_folder, _ = Folder.objects.get_or_create(
                user=user,
                name=folder_name,
                parent=current_folder
            )

    # 💾 save final file
    ext = os.path.splitext(session.filename)[1].lower()
    file_type = "image" if ext in IMAGE_EXTENSIONS else "file"

    user_file = UserFile(
        user=user,
        folder=current_folder,
        original_name=session.filename,
        file_type=file_type
    )

    with open(assembled_path, "rb") as fh:
        django_file = DjangoFile(fh)
        user_file.file.save(session.filename, django_file, save=False)
        user_file.save()

    # 🧹 cleanup
    shutil.rmtree(upload_dir, ignore_errors=True)

    # ⚙️ async jobs
    if user_file.file_type == "image":
        generate_thumbnail.delay(user_file.id)
        extract_face_embeddings.delay(user_file.id)

    return JsonResponse({"success": True})

# ============================
# PUBLIC SHARED FOLDER VIEW
# ============================
def shared_folder_view(request, token, folder_id=None):
    share = get_object_or_404(FolderShare, token=token)

    if folder_id:
        folder = get_object_or_404(Folder, id=folder_id)
    else:
        folder = share.folder

    folders = Folder.objects.filter(parent=folder).order_by("name")
    files = UserFile.objects.filter(folder=folder).order_by("numeric_key", "original_name")

    return render(request, "filemanager/shared_folder.html", {
        "folder": folder,
        "folders": folders,
        "files": files,
        "allow_download": share.allow_download,
        "share_token": share.token,
    })


# ============================
# SECURE FILE DOWNLOAD
# ============================
def shared_file_download(request, token, file_id):
    share = get_object_or_404(FolderShare, token=token)

    if not share.allow_download:
        return HttpResponseForbidden("Download not allowed")

    all_folders = [share.folder] + get_all_subfolders(share.folder)

    file = get_object_or_404(
        UserFile,
        id=file_id,
        folder__in=all_folders
    )


    return FileResponse(
        file.file.open("rb"),
        as_attachment=True,
        filename=file.original_name
    )

@login_required
def create_photo_album(request, folder_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    folder = get_object_or_404(
        Folder,
        id=folder_id,
        user=request.user
    )

    # prevent duplicate album
    if hasattr(folder, "photo_album"):
        return JsonResponse(
            {"error": "Album already exists for this folder"},
            status=400
        )

    album_name = request.POST.get("album_name")
    event_date = request.POST.get("event_date")
    allow_download = request.POST.get("allow_download") == "true"
    watermark = request.POST.get("watermark") == "true"
    pin = request.POST.get("pin")

    cover = request.FILES.get("cover_image")

    # Validate required fields
    if not album_name or not event_date:
        return JsonResponse(
            {"error": "Album name and event date required"},
            status=400
        )

    # Require a 4-digit PIN for public albums created here
    if not pin:
        return JsonResponse({"error": "PIN is required"}, status=400)

    if len(pin) != 4 or not pin.isdigit():
        return JsonResponse({"error": "PIN must be 4 digits"}, status=400)

    album = PhotoAlbum.objects.create(
        user=request.user,
        folder=folder,
        album_name=album_name,
        event_date=event_date,
        allow_download=allow_download,
        watermark=watermark,
        pin=pin,
        cover_image=cover
    )

    return JsonResponse({
        "success": True,
        "album_id": album.id
    })

def public_album_detail(request, token):
    album = get_object_or_404(
        PhotoAlbum,
        public_token=token
    )

    if album.pin:
        session_key = f"album_full_access_{album.public_token}"
        if not request.session.get(session_key):
            return render(
                request,
                "filemanager/album_pin.html",  # 👈 THIS TEMPLATE
                {"album": album}
            )
        
    folder = album.folder

    all_folders = [album.folder] + get_all_subfolders(album.folder)

    files = UserFile.objects.filter(
        folder__in=all_folders
    ).order_by("numeric_key", "original_name")

    return render(
        request,
        "filemanager/album_public.html",
        {
            "album": album,
            "files": files,
            "allow_download": album.allow_download,
            "share_token": album.public_token,
        }
    )


def photo_album_verify_pin(request, token):
    album = get_object_or_404(
        PhotoAlbum,
        public_token=token
    )

    if request.method == "POST":
        pin = request.POST.get("pin")

        if pin == album.pin:
            request.session[
                f"album_full_access_{album.public_token}"
            ] = True

            return JsonResponse({"success": True})

        return JsonResponse(
            {"success": False, "error": "Invalid PIN"},
            status=400
        )

    return JsonResponse(
        {"success": False, "error": "Invalid request"},
        status=400
    )

@login_required
def toggle_album_download(request, album_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    album = get_object_or_404(
        PhotoAlbum,
        id=album_id,
        user=request.user
    )

    allow = request.POST.get("allow") == "true"
    album.allow_download = allow
    album.save()

    return JsonResponse({
        "success": True,
        "allow_download": album.allow_download
    })


@login_required
def photo_album_detail(request, album_id, folder_id=None):
    album = get_object_or_404(
        PhotoAlbum,
        id=album_id,
        user=request.user
    )

    # which folder to show
    if folder_id:
        folder = get_object_or_404(
            Folder,
            id=folder_id,
            user=request.user
        )
    else:
        folder = album.folder

    subfolders = Folder.objects.filter(
        parent=folder,
        user=request.user
    ).order_by("name")

    files = UserFile.objects.filter(
        folder=folder,
        user=request.user
    ).order_by("numeric_key", "original_name")

    return render(
        request,
        "filemanager/album_detail.html",
        {
            "album": album,
            "folder": folder,
            "folders": subfolders,
            "files": files,
        }
    )


@login_required
def photo_album_list(request):
    albums = PhotoAlbum.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "filemanager/album_list.html", {
        "albums": albums
    })

@login_required
def photo_album_edit(request, album_id):
    album = get_object_or_404(
        PhotoAlbum,
        id=album_id,
        user=request.user
    )

    if request.method == "POST":
        album.album_name = request.POST.get("album_name")
        album.event_date = request.POST.get("event_date")
        album.allow_download = request.POST.get("allow_download") == "on"
        album.watermark = request.POST.get("watermark") == "on"

        # Optional PIN update
        new_pin = request.POST.get("pin")
        if new_pin:
            if len(new_pin) != 4 or not new_pin.isdigit():
                return JsonResponse({"error": "PIN must be 4 digits"}, status=400)
            album.pin = new_pin

        if request.FILES.get("cover_image"):
            album.cover_image = request.FILES["cover_image"]

        album.save()
        return redirect("photo_album_list")

    return render(
        request,
        "filemanager/photo_album_edit.html",
        {"album": album}
    )

@login_required
def photo_album_set_pin(request, album_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    album = get_object_or_404(
        PhotoAlbum,
        id=album_id,
        user=request.user
    )

    pin = request.POST.get("pin")

    if pin and len(pin) != 4:
        return JsonResponse(
            {"error": "PIN must be 4 digits"},
            status=400
        )

    album.pin = pin
    album.save()

    return JsonResponse({"success": True})

@login_required
def photo_album_delete(request, album_id):
    album = get_object_or_404(
        PhotoAlbum,
        id=album_id,
        user=request.user
    )

    folder_id = album.folder.id
    album.delete()

    return redirect("photo_album_list")

def album_face_search_view(request, token):
    album = get_object_or_404(PhotoAlbum, public_token=token)

    return render(request, "filemanager/face_search.html", {
        "album": album
    })

@login_required
def album_customers(request, album_id):
    album = get_object_or_404(PhotoAlbum, id=album_id)

    customers = FaceSearchLog.objects.filter(album=album).order_by("-searched_at")

    return render(request, "filemanager/album_customers.html", {
        "album": album,
        "customers": customers
    })

def face_search_page(request):
    return render(request, "filemanager/face_search.html")


def home_page(request):
    """Public home page shown at site root"""
    return render(request, "filemanager/home.html")


@csrf_exempt
def search_selfie(request):
    visitor_name = request.POST.get("visitor_name")
    visitor_mobile = request.POST.get("visitor_mobile")

    if not visitor_name or not visitor_mobile:
        return JsonResponse({"error": "Visitor details missing"}, status=400)
    
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    # 1️⃣ Get album token
    album_token = request.POST.get("album_token")
    if not album_token:
        return JsonResponse({"error": "Album token missing"}, status=400)

    try:
        album = PhotoAlbum.objects.get(public_token=album_token)
    except PhotoAlbum.DoesNotExist:
        return JsonResponse({"error": "Invalid album"}, status=404)

    # 2️⃣ Get selfie
    image_data = request.POST.get("selfie")
    if not image_data or ";base64," not in image_data:
        return JsonResponse({"error": "Invalid selfie data"}, status=400)

    try:
        _, imgstr = image_data.split(";base64,")
        image_bytes = base64.b64decode(imgstr)
    except Exception:
        return JsonResponse({"error": "Selfie decode failed"}, status=400)

    # 3️⃣ Save selfie temp
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(image_bytes)
        selfie_path = tmp.name

    query_embedding = extract_single_face(selfie_path)
    os.remove(selfie_path)

    if query_embedding is None:
        return JsonResponse({"error": "No face detected"}, status=400)

    # 4️⃣ Get face embeddings ONLY from this album
    # Get files in this album first
    all_folders = [album.folder] + get_all_subfolders(album.folder)

    files_in_album = UserFile.objects.filter(folder__in=all_folders)
    faces = FaceEmbedding.objects.filter(file__in=files_in_album)

    if not faces.exists():
        return JsonResponse({"images": []})

    embeddings = []
    file_ids = []

    for face in faces:
        embeddings.append(np.frombuffer(face.embedding, dtype=np.float32))
        file_ids.append(face.file.id)

    X = np.array(embeddings).astype("float32")
    faiss.normalize_L2(X)

    index = faiss.IndexFlatIP(X.shape[1])
    index.add(X)

    q = query_embedding.reshape(1, -1).astype("float32")
    faiss.normalize_L2(q)

    D, I = index.search(q, 100)

    matched_file_ids = {
        file_ids[idx]
        for score, idx in zip(D[0], I[0])
        if score >= 0.6
    }

    files = UserFile.objects.filter(id__in=matched_file_ids)

    # ✅ SAVE VISITOR SEARCH LOG
    FaceSearchLog.objects.create(
        album=album,
        visitor_name=visitor_name,
        visitor_mobile=visitor_mobile,
        match_count=files.count()
    )

    images = [{
        "id": f.id,
        "url": f.file.url,
        "name": os.path.basename(f.file.name)
    } for f in files]

    return JsonResponse({
        "images": images
    })


@csrf_exempt
def download_search_matches(request):
    """Create a ZIP of the requested file ids (must belong to the album) and return as attachment."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    album_token = data.get('album_token')
    file_ids = data.get('file_ids') or []

    if not album_token or not file_ids:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    try:
        album = PhotoAlbum.objects.get(public_token=album_token)
    except PhotoAlbum.DoesNotExist:
        return JsonResponse({"error": "Invalid album"}, status=404)

    all_folders = [album.folder] + get_all_subfolders(album.folder)
    files = UserFile.objects.filter(id__in=file_ids, folder__in=all_folders)

    if not files.exists():
        return JsonResponse({"error": "No files found"}, status=404)

    # Create ZIP in memory (for moderate number of files)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zf:
        for f in files:
            try:
                file_path = f.file.path
                arcname = os.path.basename(f.file.name)
                if os.path.exists(file_path):
                    zf.write(file_path, arcname=arcname)
            except Exception:
                continue

    buffer.seek(0)
    resp = HttpResponse(buffer.read(), content_type='application/zip')
    resp['Content-Disposition'] = f'attachment; filename="matches-{int(time.time())}.zip"'
    return resp

@login_required
def apply_to_announcement(request, announcement_id):
    announcement = get_object_or_404(Announcement, id=announcement_id)

    # 🚫 Owner cannot apply
    if announcement.user == request.user:
        messages.error(request, "You cannot apply to your own announcement.")
        return redirect("announcements_list")

    # Optional: check expired
    from django.utils import timezone
    if announcement.end_date < timezone.localdate():
        messages.error(request, "This announcement is expired.")
        return redirect("announcements_list")

    # ✅ Continue apply logic here
    Applicant.objects.create(
        announcement=announcement,
        user=request.user
    )

    messages.success(request, "Applied successfully!")
    return redirect("announcements_list")

@login_required
def announcements_list(request):
    city_query = request.GET.get('city', '')
    state_query = request.GET.get('state', '')

    today = timezone.localdate()  # IMPORTANT: DateField → use localdate()

    # ✅ Only active announcements
    all_announcements = Announcement.objects.filter(
        end_date__gte=today
    ).order_by("-created_at")
    applied_ids = set(
        Applicant.objects
        .filter(user=request.user)
        .values_list('announcement_id', flat=True)
    )
    if city_query:
        all_announcements = all_announcements.filter(city__icontains=city_query)

    if state_query:
        all_announcements = all_announcements.filter(state__icontains=state_query)

    visible = []
    for a in all_announcements:
        if a.visibility == "public":
            visible.append(a)
        elif a.visibility == "staff" and request.user.is_staff:
            visible.append(a)
        elif a.user == request.user:
            visible.append(a)

    return render(
        request,
        "filemanager/announcements_list.html",
        {"announcements": visible}
    )

@login_required
def announcement_create(request):
    if request.method == "POST":
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            ann = form.save(commit=False)
            ann.user = request.user
            ann.save()
            return redirect("announcements_list")
    else:
        form = AnnouncementForm()

    return render(request, "filemanager/announcement_form.html", {"form": form})

@login_required
def calendar_view(request):
    """Display calendar view with all events"""
    month = int(request.GET.get('month', timezone.now().month))
    year = int(request.GET.get('year', timezone.now().year))
    
    # Get current month and year for context
    current_month = datetime(year, month, 1)
    today = timezone.now().date()
    
    # Get previous and next month
    if month == 1:
        prev_month = datetime(year - 1, 12, 1)
    else:
        prev_month = datetime(year, month - 1, 1)
    
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    
    # Build calendar grid
    cal = calendar.monthcalendar(year, month)
    
    # Get all events for the user in this month
    events = CalendarEvent.objects.filter(
        created_by=request.user,
        start_date__year=year,
        start_date__month=month
    ).order_by('start_date')
    
    # Convert calendar grid to date objects
    calendar_grid = []
    for week in cal:
        week_dates = []
        for day in week:
            if day == 0:
                week_dates.append(None)
            else:
                week_dates.append(datetime(year, month, day).date())
        calendar_grid.append(week_dates)
    
    return render(request, "filemanager/calendar_view.html", {
        "calendar": calendar_grid,
        "current_month": current_month,
        "today": today,
        "prev_month": prev_month,
        "next_month": next_month,
        "events": events,
    })


@login_required
def calendar_events_list(request):
    """List all calendar events created by the user"""
    events = CalendarEvent.objects.filter(created_by=request.user).order_by("start_date")
    return render(request, "filemanager/calendar_events_list.html", {"events": events})


@login_required
def calendar_event_create(request):
    """Create a new calendar event"""
    if request.method == "POST":
        form = CalendarEventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.created_by = request.user
            event.save()
            return redirect("calendar_events_list")
    else:
        form = CalendarEventForm()

    return render(request, "filemanager/calendar_event_form.html", {"form": form})


@login_required
def calendar_event_detail(request, pk):
    """View details of a specific calendar event"""
    event = CalendarEvent.objects.get(pk=pk, created_by=request.user)
    return render(request, "filemanager/calendar_event_detail.html", {"event": event})


@login_required
def calendar_event_update(request, pk):
    """Update an existing calendar event"""
    event = CalendarEvent.objects.get(pk=pk, created_by=request.user)
    
    if request.method == "POST":
        form = CalendarEventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            return redirect("calendar_event_detail", pk=event.pk)
    else:
        form = CalendarEventForm(instance=event)

    return render(request, "filemanager/calendar_event_form.html", {"form": form, "event": event})


@login_required
def calendar_event_delete(request, pk):
    """Delete a calendar event"""
    event = CalendarEvent.objects.get(pk=pk, created_by=request.user)
    
    if request.method == "POST":
        event.delete()
        return redirect("calendar_events_list")

    return render(request, "filemanager/calendar_event_confirm_delete.html", {"event": event})


@login_required
@csrf_exempt
def apply_announcement(request):
    """Apply for an announcement"""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"}, status=400)

    try:
        import json
        data = json.loads(request.body)
        announcement_id = data.get('announcement_id')

        announcement = Announcement.objects.get(id=announcement_id)

        # Check if already applied
        existing = Applicant.objects.filter(
            announcement=announcement,
            user=request.user
        ).exists()

        if existing:
            return JsonResponse({
                "success": False,
                "message": "You have already applied for this job"
            })

        # Create application
        Applicant.objects.create(
            announcement=announcement,
            user=request.user
        )

        return JsonResponse({
            "success": True,
            "message": "Applied successfully!"
        })

    except Announcement.DoesNotExist:
        return JsonResponse({
            "success": False,
            "message": "Announcement not found"
        }, status=404)
    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)


@login_required
def view_applicants(request):
    """View applicants for announcements created by the logged-in user"""
    # Get all announcements created by the user
    user_announcements = Announcement.objects.filter(user=request.user).order_by('-created_at')
    
    # Get all applicants for these announcements
    applicants = Applicant.objects.filter(
        announcement__user=request.user
    ).select_related('user', 'announcement').order_by('-applied_at')

    # Filter by announcement if specified
    announcement_id = request.GET.get('announcement')
    if announcement_id:
        applicants = applicants.filter(announcement_id=announcement_id)

    context = {
        'applicants': applicants,
        'user_announcements': user_announcements,
        'selected_announcement': announcement_id,
        'total_applications': applicants.count(),
    }

    return render(request, "filemanager/view_applicants.html", context)

@login_required
def my_applications(request):
    applications = (
        Applicant.objects
        .filter(user=request.user)
        .select_related('announcement')
        .order_by('-applied_at')
    )

    return render(
        request,
        'filemanager/my_applications.html',
        {'applications': applications}
    )

@login_required
@csrf_exempt
def update_applicant_status(request):
    """Update applicant status"""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"}, status=400)

    try:
        import json
        data = json.loads(request.body)
        applicant_id = data.get('applicant_id')
        status = data.get('status')

        applicant = Applicant.objects.get(id=applicant_id)

        # Check if user is the announcement creator
        if applicant.announcement.user != request.user:
            return JsonResponse({
                "success": False,
                "message": "You don't have permission to update this application"
            }, status=403)

        # Update status
        applicant.status = status
        applicant.save()

        return JsonResponse({
            "success": True,
            "message": f"Application {status} successfully!"
        })

    except Applicant.DoesNotExist:
        return JsonResponse({
            "success": False,
            "message": "Applicant not found"
        }, status=404)
    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)


@login_required
def profile(request):
    user = request.user
    file_count = UserFile.objects.filter(user=user).count()
    announcement_count = Announcement.objects.filter(user=user).count()

    profile_obj, _ = Profile.objects.get_or_create(user=user)

    storage_used_gb = round(profile_obj.storage_used / (1024 ** 3), 2)

    if profile_obj.plan:
        storage_limit_gb = profile_obj.plan.storage_limit_gb
        storage_percent = round(
            (profile_obj.storage_used / (storage_limit_gb * 1024 ** 3)) * 100, 1
        )
    else:
        storage_limit_gb = None
        storage_percent = None

    context = {
        "file_count": file_count,
        "announcement_count": announcement_count,
        "profile_obj": profile_obj,
        "storage_used_gb": storage_used_gb,
        "storage_limit_gb": storage_limit_gb,
        "storage_percent": storage_percent,
        "active": "overview",
    }

    return render(request, "filemanager/profile.html", context)



@login_required
def profile_edit(request):
    user = request.user
    profile_obj, _ = Profile.objects.get_or_create(user=user)

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully")
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile_obj)

    return render(request, "filemanager/profile.html", {
        "active": "edit",
        "form": form,
        "profile_obj": profile_obj,
    })


@login_required
def change_password(request):
    if request.method == "POST":
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password changed successfully")
            return redirect("profile")
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, "filemanager/profile.html", {
        "active": "change_password",
        "form": form,
    })


@login_required
def seller_request(request):
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = SellerRequestForm(request.POST, instance=profile_obj)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.seller_status = "pending"
            profile.save()
            messages.success(request, "Seller request submitted")
            return redirect("profile")
    else:
        form = SellerRequestForm(instance=profile_obj)

    return render(request, "filemanager/profile.html", {
        "active": "seller_request",
        "form": form,
        "profile_obj": profile_obj,
    })


@login_required
def portfolio_edit(request):
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Portfolio updated")
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile_obj)

    return render(request, "filemanager/profile.html", {
        "active": "portfolio",
        "form": form,
        "profile_obj": profile_obj,
    })


def user_logout(request):
    """Logout user and redirect to login page"""
    logout(request)
    return redirect("login")


def login_view(request):
    """Login page and authentication"""
    if request.user.is_authenticated:
        return redirect("file_manager")
    
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect("file_manager")
        else:
            return render(request, "filemanager/login.html", {
                "error": "Invalid username or password"
            })
    
    return render(request, "filemanager/login.html")

from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.shortcuts import render, redirect

def signup_view(request):
    if request.method == "POST":

        phone = request.POST.get("phone")
        password = request.POST.get("password")
        password_confirm = request.POST.get("password_confirm")
        username = request.POST.get("username") or phone
        email = request.POST.get("email")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")

        # validate
        if not phone or not password:
            return render(request, "filemanager/signup.html", {
                "error": "Missing required fields"
            })

        if password != password_confirm:
            return render(request, "filemanager/signup.html", {
                "error": "Passwords do not match"
            })

        if not phone.isdigit() or len(phone) != 10:
            return render(request, "filemanager/signup.html", {
                "error": "Phone must be 10 digits"
            })

        if User.objects.filter(username=username).exists():
            return render(request, "filemanager/signup.html", {
                "error": "User already exists"
            })

        try:
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name or "",
                last_name=last_name or ""
            )
        except IntegrityError:
            return render(request, "filemanager/signup.html", {
                "error": "User creation failed"
            })

        # assign plan
        from .models import Plan, Profile
        plan = Plan.objects.filter(storage_limit_gb=10, price=0).first()
        profile, _ = Profile.objects.get_or_create(user=user)
        if plan:
            profile.plan = plan
            profile.save()

        login(request, user)
        return redirect("file_manager")   # or dashboard

    return render(request, "filemanager/signup.html")
