from celery import shared_task
from django.core.files.base import ContentFile
from PIL import Image, ImageFile
from io import BytesIO
import os
import rawpy
import subprocess
from django.db import transaction
from .models import UserFile, FaceEmbedding, ArchiveJob
from .utils import extract_faces

# -----------------------------
# PIL SAFETY SETTINGS
# -----------------------------
Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True

RAW_EXTENSIONS = [
    ".cr2", ".cr3", ".nef", ".arw", ".dng",
    ".raf", ".orf", ".rw2", ".pef"
]


@shared_task(bind=True)
def generate_thumbnail(self, user_file_id):

    try:
        user_file = UserFile.objects.filter(id=user_file_id).first()
        if not user_file:
            return "UserFile not found"

        if user_file.file_type != "image":
            return "Not image"

        path = user_file.file.path
        if not os.path.exists(path):
            return "Missing file"

        ext = os.path.splitext(user_file.original_name)[1].lower()

        # =========================
        # SAFE LOAD (LOW MEMORY)
        # =========================
        try:
            if ext in RAW_EXTENSIONS:
                with rawpy.imread(path) as raw:
                    rgb = raw.postprocess(
                        half_size=True,      # 🔴 critical
                        use_camera_wb=True
                    )
                img = Image.fromarray(rgb)

            else:
                img = Image.open(path)

                # 🔴 THIS prevents huge memory decode
                img.thumbnail((2500, 2500), Image.BILINEAR)

        except Exception as e:
            print("Load fail:", e)
            return "load_failed"

        img = img.convert("RGB")

        # =========================
        # THUMB ONLY FIRST (cheap)
        # =========================
        thumb = img.copy()
        thumb.thumbnail((300, 300), Image.BILINEAR)

        buf = BytesIO()
        thumb.save(buf, "JPEG", quality=70)
        buf.seek(0)

        user_file.thumbnail.save(
            f"thumb_{user_file.id}.jpg",
            ContentFile(buf.read()),
            save=False
        )

        # =========================
        # PREVIEW — OPTIONAL LIGHT
        # =========================
        try:
            preview = img.copy()
            preview.thumbnail((1400, 1400), Image.BILINEAR)

            buf2 = BytesIO()
            preview.save(buf2, "JPEG", quality=85)
            buf2.seek(0)

            user_file.preview.save(
                f"preview_{user_file.id}.jpg",
                ContentFile(buf2.read()),
                save=False
            )
        except Exception as e:
            print("Preview skip:", e)

        user_file.save()
        return "thumb_ok"

    except Exception as e:
        print("Thumbnail crash:", e)
        return "thumb_crash"

# =========================================================
# FACE EMBEDDING EXTRACTION (JPEG/PNG ONLY)
# =========================================================

FACE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]


@shared_task(bind=True)
def extract_face_embeddings(self, user_file_id):

    try:
        user_file = UserFile.objects.get(id=user_file_id)
    except UserFile.DoesNotExist:
        return "UserFile not found"

    if user_file.file_type != "image":
        return "Not image"

    img_path = user_file.file.path
    if not os.path.exists(img_path):
        return "Image path not found"

    ext = os.path.splitext(user_file.original_name)[1].lower()

    # ✅ SKIP RAW FACE DETECTION
    if ext not in FACE_EXTENSIONS:
        print("Skipping face detection for:", ext)
        return "face_skip_non_jpeg"

    # ---------- SAFE FACE EXTRACTION ----------
    try:
        faces = extract_faces(img_path)
    except Exception as e:
        print("extract_faces crashed:", e)
        return "face_extract_failed"

    if not faces:
        print("No faces detected:", user_file.id)
        FaceEmbedding.objects.filter(file=user_file).delete()
        return "no_faces"

    # ---------- SAVE EMBEDDINGS ----------
    FaceEmbedding.objects.filter(file=user_file).delete()

    saved = 0
    for face in faces:
        try:
            FaceEmbedding.objects.create(
                user=user_file.user,
                file=user_file,
                embedding=face.tobytes()
            )
            saved += 1
        except Exception as e:
            print("Embedding save failed:", e)

    return f"{saved} faces saved"

@shared_task(bind=True)
def build_archive(self, job_id, file_ids):

    import zipfile
    import os
    from django.conf import settings
    from .models import ArchiveJob, UserFile

    try:
        job = ArchiveJob.objects.get(id=job_id)
        job.status = "processing"
        job.progress = 1
        job.save()

        files = UserFile.objects.filter(id__in=file_ids)
        total = files.count()

        if total == 0:
            job.status = "failed"
            job.save()
            return

        zip_path = os.path.join(
            settings.MEDIA_ROOT,
            f"archives/job_{job.id}.zip"
        )

        os.makedirs(os.path.dirname(zip_path), exist_ok=True)

        with zipfile.ZipFile(
            zip_path,
            "w",
            compression=zipfile.ZIP_STORED,
            allowZip64=True
        ) as zf:

            for i, f in enumerate(files, start=1):

                if f.file and os.path.exists(f.file.path):
                    zf.write(
                        f.file.path,
                        arcname=f.original_name
                    )

                percent = int((i / total) * 100)

                ArchiveJob.objects.filter(id=job_id)\
                    .update(progress=percent)

        job.temp_path = zip_path
        job.status = "ready"
        job.progress = 100
        job.save()

    except Exception as e:
        print("Archive build failed:", e)
        ArchiveJob.objects.filter(id=job_id).update(
            status="failed"
        )
