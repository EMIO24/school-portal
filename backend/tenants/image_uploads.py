from io import BytesIO
import uuid

from PIL import Image, UnidentifiedImageError
from django.core.files.storage import default_storage
from rest_framework import serializers


IMAGE_TYPES = {'PNG': 'png', 'JPEG': 'jpg', 'WEBP': 'webp'}
IMAGE_MIMES = {'image/png', 'image/jpeg', 'image/webp'}
MAX_IMAGE_BYTES = 2 * 1024 * 1024


def store_uploaded_image(upload, folder, max_bytes=MAX_IMAGE_BYTES):
    if not upload:
        raise serializers.ValidationError({'image': 'Choose an image file.'})
    if upload.size > max_bytes:
        raise serializers.ValidationError({'image': 'Image must be 2 MB or smaller.'})
    if upload.content_type not in IMAGE_MIMES:
        raise serializers.ValidationError({'image': 'Use a PNG, JPEG or WebP image.'})
    try:
        content = upload.read()
        image = Image.open(BytesIO(content))
        image.verify()
        extension = IMAGE_TYPES.get(image.format)
    except (UnidentifiedImageError, OSError, ValueError):
        extension = None
    if not extension:
        raise serializers.ValidationError({'image': 'The selected file is not a valid PNG, JPEG or WebP image.'})
    upload.seek(0)
    name = default_storage.save(f'{folder}/{uuid.uuid4().hex}.{extension}', upload)
    return default_storage.url(name)
