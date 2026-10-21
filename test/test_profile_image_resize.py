import importlib.util
import io
import sys
from pathlib import Path

from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parents[1] / 'backend'
MODULE_PATH = BACKEND_DIR / 'open_webui' / 'utils' / 'profile_image.py'
spec = importlib.util.spec_from_file_location('profile_image', MODULE_PATH)
profile_image = importlib.util.module_from_spec(spec)
sys.modules['profile_image'] = profile_image
assert spec.loader is not None
spec.loader.exec_module(profile_image)

normalize_width = profile_image.normalize_width
resize_image_bytes = profile_image.resize_image_bytes
PROFILE_IMAGE_MAX_WIDTH = profile_image.PROFILE_IMAGE_MAX_WIDTH


def make_image(width, height, fmt, mode='RGBA'):
    if fmt == 'JPEG':
        mode = 'RGB'
    image = Image.new(mode, (width, height), (200, 30, 30, 255) if mode == 'RGBA' else (200, 30, 30))
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def decode(data):
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        return image.format, image.size


def test_normalize_width_clamps_and_rejects_junk():
    assert normalize_width(None) is None
    assert normalize_width(0) is None
    assert normalize_width(-5) is None
    assert normalize_width('abc') is None
    assert normalize_width(60) == 60
    assert normalize_width('60') == 60
    assert normalize_width(99999) == PROFILE_IMAGE_MAX_WIDTH


def test_square_avatar_is_downscaled_in_each_allowed_format():
    for fmt, media_type in (('PNG', 'image/png'), ('WEBP', 'image/webp'), ('JPEG', 'image/jpeg')):
        data, out_type = resize_image_bytes(make_image(250, 250, fmt), media_type, 60)
        assert out_type == media_type
        assert decode(data) == (fmt, (60, 60))


def test_aspect_ratio_is_preserved():
    data, _ = resize_image_bytes(make_image(400, 200, 'PNG'), 'image/png', 60)
    assert decode(data)[1] == (60, 30)
    data, _ = resize_image_bytes(make_image(200, 400, 'PNG'), 'image/png', 60)
    assert decode(data)[1] == (30, 60)


def test_small_images_are_never_upscaled_and_bytes_are_untouched():
    original = make_image(40, 40, 'PNG')
    data, out_type = resize_image_bytes(original, 'image/png', 60)
    assert data == original
    assert out_type == 'image/png'


def test_gif_is_returned_unchanged():
    original = make_image(250, 250, 'GIF', mode='P')
    data, out_type = resize_image_bytes(original, 'image/gif', 60)
    assert data == original
    assert out_type == 'image/gif'


def test_palette_png_resizes_cleanly():
    data, _ = resize_image_bytes(make_image(250, 250, 'PNG', mode='P'), 'image/png', 60)
    assert decode(data) == ('PNG', (60, 60))


def test_unsupported_media_type_raises():
    try:
        resize_image_bytes(make_image(250, 250, 'PNG'), 'image/svg+xml', 60)
    except ValueError:
        return
    raise AssertionError('expected ValueError for unsupported media type')


def test_undecodable_bytes_raise_so_caller_can_fall_back():
    try:
        resize_image_bytes(b'not an image', 'image/png', 60)
    except Exception:
        return
    raise AssertionError('expected an exception for undecodable data')
