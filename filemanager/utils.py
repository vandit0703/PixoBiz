import cv2
import numpy as np
from insightface.app import FaceAnalysis

# load model once (IMPORTANT)
app = FaceAnalysis(name="buffalo_l")
app.prepare(ctx_id=0, det_size=(640, 640))

def extract_faces(image_path):
    img = cv2.imread(image_path)
    faces = app.get(img)

    embeddings = []
    for face in faces:
        embeddings.append(face.normed_embedding)

    return embeddings


def extract_single_face(image_path):
    faces = extract_faces(image_path)
    return faces[0] if faces else None
