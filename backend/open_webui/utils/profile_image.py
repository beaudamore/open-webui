"""
Helpers for serving profile / model avatar images at a requested size.

Open WebUI stores model avatars as data URIs (the model editor normalizes
uploads to 250x250). The frontend shrinks them with CSS, but anything that
embeds the image URL in message content (pipelines, functions, tools) gets the
full-size file, because markdown images render at native pixel size. The
``/api/v1/models/model/profile/image`` endpoint therefore accepts an optional
``width`` query parameter and uses these helpers to downscale on the fly.
"""

from __future__ import annotations

import io

from PIL import Image

# Upper bound for the requested width. Avatars are stored at 250px, so anything
# larger is pointless; the cap also bounds CPU and memory spent per request.
PROFILE_IMAGE_MAX_WIDTH = 512

# Pillow format names for the raster types the endpoint is allowed to serve.
_FORMAT_BY_MEDIA_TYPE = {
    'image/png': 'PNG',
    'image/jpeg': 'JPEG',
    'image/webp': 'WEBP',
}


def normalize_width(width: int | None) -> int | None:
    """
    Clamp a requested width to [1, PROFILE_IMAGE_MAX_WIDTH].

    Returns None when no usable width was requested, so callers can serve the
    stored image unchanged.
    """
    if width is None:
        return None
    try:
        width = int(width)
    except (TypeError, ValueError):
        return None
    if width < 1:
        return None
    return min(width, PROFILE_IMAGE_MAX_WIDTH)


def resize_image_bytes(data: bytes, media_type: str, width: int) -> tuple[bytes, str]:
    """
    Downscale raster image bytes so neither side exceeds ``width``.

    - Aspect ratio is preserved (a 400x200 image at width 60 becomes 60x30).
    - Images that already fit are returned unchanged; nothing is ever upscaled.
    - GIFs are returned unchanged to keep animation intact.
    - Output keeps the input format (PNG, JPEG or WebP).

    Returns ``(bytes, media_type)``. Raises ``ValueError`` for an unsupported
    media type and lets Pillow errors propagate for undecodable data, so the
    caller can fall back to the original bytes.
    """
    media_type = (media_type or '').lower()
    if media_type == 'image/gif':
        return data, media_type

    pil_format = _FORMAT_BY_MEDIA_TYPE.get(media_type)
    if pil_format is None:
        raise ValueError(f'Unsupported media type for resize: {media_type}')

    with Image.open(io.BytesIO(data)) as image:
        image.load()
        if image.width <= width and image.height <= width:
            return data, media_type

        resized = image.copy()
        resized.thumbnail((width, width), Image.Resampling.LANCZOS)

        if pil_format == 'JPEG' and resized.mode not in ('RGB', 'L'):
            resized = resized.convert('RGB')
        elif pil_format in ('PNG', 'WEBP') and resized.mode == 'P':
            resized = resized.convert('RGBA')

        buffer = io.BytesIO()
        save_kwargs = {'optimize': True} if pil_format == 'PNG' else {'quality': 85}
        resized.save(buffer, format=pil_format, **save_kwargs)
        return buffer.getvalue(), media_type
