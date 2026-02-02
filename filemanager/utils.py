import cv2
import numpy as np
import os
import rawpy
from insightface.app import FaceAnalysis

# ==============================
# RAW extension support
# ==============================
RAW_EXTENSIONS = [
    ".cr2",".cr3",".nef",".arw",".dng",".raf",".orf",".rw2",".pef"
]

# ==============================
# Universal image loader
# ==============================
def load_image_any(image_path):
    ext = os.path.splitext(image_path)[1].lower()

    # ✅ RAW → decode with rawpy
    if ext in RAW_EXTENSIONS:
        with rawpy.imread(image_path) as raw:
            rgb = raw.postprocess()
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    # ✅ Normal → cv2
    return cv2.imread(image_path)


# ==============================
# InsightFace model (load once)
# ==============================
app = FaceAnalysis(name="buffalo_l")
app.prepare(ctx_id=0, det_size=(640, 640))


# ==============================
# Face extraction
# ==============================
def extract_faces(image_path):

    img = load_image_any(image_path)

    if img is None:
        print("Image load failed:", image_path)
        return []

    faces = app.get(img)

    embeddings = []
    for face in faces:
        embeddings.append(face.normed_embedding)

    return embeddings


def extract_single_face(image_path):
    faces = extract_faces(image_path)
    return faces[0] if faces else None
