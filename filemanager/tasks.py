from celery import shared_task
from django.core.files.base import ContentFile
from PIL import Image
from io import BytesIO
import os

from .models import UserFile, FaceEmbedding
from .utils import extract_faces

Image.MAX_IMAGE_PIXELS = None

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=10, retry_kwargs={'max_retries': 3})
def generate_thumbnail(self, user_file_id):
    try:
        user_file = UserFile.objects.get(id=user_file_id)
    except UserFile.DoesNotExist:
        return "UserFile not found"

    if user_file.file_type != "image":
        return "Not image"

    if user_file.thumbnail:
        return "Thumbnail already exists"

    img_path = user_file.file.path
    if not os.path.exists(img_path):
        return "Image path not found"

    with Image.open(img_path) as img:
        img = img.convert("RGB")
        img.thumbnail((300, 300), Image.LANCZOS)

        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=75, optimize=True)
        buffer.seek(0)

        thumb_name = f"thumb_{os.path.basename(user_file.file.name)}.jpg"
        user_file.thumbnail.save(thumb_name, ContentFile(buffer.read()), save=True)

    return f"Thumbnail done for {user_file.id}"

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
