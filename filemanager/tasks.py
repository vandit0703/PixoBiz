from celery import shared_task
from django.core.files.base import ContentFile
from PIL import Image
from io import BytesIO
import os
import rawpy
import imageio

from .models import UserFile, FaceEmbedding
from .utils import extract_faces

Image.MAX_IMAGE_PIXELS = None

RAW_EXTENSIONS = [
    ".cr2",".cr3",".nef",".arw",".dng",".raf",".orf",".rw2",".pef"
]

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=10, retry_kwargs={'max_retries': 3})
def generate_thumbnail(self, user_file_id):

    user_file = UserFile.objects.filter(id=user_file_id).first()
    if not user_file:
        return "UserFile not found"

    if user_file.file_type != "image":
        return "Not image"

    img_path = user_file.file.path
    if not os.path.exists(img_path):
        return "Missing file"

    ext = os.path.splitext(user_file.original_name)[1].lower()
    print("THUMB EXT:", ext)

    # ---------- LOAD IMAGE ----------
    if ext in RAW_EXTENSIONS:
        with rawpy.imread(img_path) as raw:
            rgb = raw.postprocess(
                use_camera_wb=True,
                half_size=False,
                no_auto_bright=True
            )
        img = Image.fromarray(rgb)
    else:
        img = Image.open(img_path)

    img = img.convert("RGB")

    # ---------- PREVIEW (BIG) ----------
    preview_img = img.copy()
    preview_img.thumbnail((1600, 1600), Image.LANCZOS)

    preview_buffer = BytesIO()
    preview_img.save(preview_buffer, format="JPEG", quality=90)
    preview_buffer.seek(0)

    user_file.preview.save(
        f"preview_{user_file.id}.jpg",
        ContentFile(preview_buffer.read()),
        save=False
    )

    # ---------- THUMBNAIL (SMALL) ----------
    thumb_img = img.copy()
    thumb_img.thumbnail((300, 300), Image.LANCZOS)

    thumb_buffer = BytesIO()
    thumb_img.save(thumb_buffer, format="JPEG", quality=75, optimize=True)
    thumb_buffer.seek(0)

    user_file.thumbnail.save(
        f"thumb_{user_file.id}.jpg",
        ContentFile(thumb_buffer.read()),
        save=False
    )

    user_file.save()

    return f"Preview + Thumbnail done {user_file.id}"

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=30, retry_kwargs={'max_retries': 2})
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

    faces = extract_faces(img_path)

    FaceEmbedding.objects.filter(file=user_file).delete()

    for face in faces:
        FaceEmbedding.objects.create(
            user=user_file.user,
            file=user_file,
            embedding=face.tobytes()
        )

    return f"Faces extracted for {user_file.id}"
