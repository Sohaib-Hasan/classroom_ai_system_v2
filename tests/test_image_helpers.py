import io

from PIL import Image

from image_helpers import resize_image_for_upload


def _make_test_image(width, height, mode="RGB", color=(255, 0, 0)):
    """Chhoti, in-memory synthetic test image — koi external file nahi
    chahiye, test fast aur self-contained rehta hai."""
    img = Image.new(mode, (width, height), color)
    buf = io.BytesIO()
    fmt = "PNG" if mode == "RGBA" else "JPEG"
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf


class TestResizeImageForUpload:
    """Build-order item 5 (Aug 2026), v0. Student phone photos resize
    karne ka logic — real PIL operations se test, koi mocking nahi
    (ye function ka poora point hi actual image processing hai)."""

    def test_small_image_is_not_upscaled(self):
        # max_width se choti image — width badhni nahi chahiye
        small = _make_test_image(400, 300)
        jpeg_bytes, mime_type = resize_image_for_upload(small, max_width=1600)

        result_img = Image.open(io.BytesIO(jpeg_bytes))
        assert result_img.width == 400
        assert result_img.height == 300
        assert mime_type == "image/jpeg"

    def test_large_image_is_resized_to_max_width(self):
        # max_width se badi image — width exactly max_width tak aani chahiye,
        # height proportionally scale honi chahiye (aspect ratio preserve)
        large = _make_test_image(3200, 2400)  # 4:3 aspect ratio
        jpeg_bytes, mime_type = resize_image_for_upload(large, max_width=1600)

        result_img = Image.open(io.BytesIO(jpeg_bytes))
        assert result_img.width == 1600
        assert result_img.height == 1200  # 4:3 preserved

    def test_output_is_always_valid_jpeg(self):
        img = _make_test_image(800, 600)
        jpeg_bytes, mime_type = resize_image_for_upload(img)

        # Agar ye JPEG-parseable nahi hai to Image.open() khud crash karega
        result_img = Image.open(io.BytesIO(jpeg_bytes))
        assert result_img.format == "JPEG"
        assert mime_type == "image/jpeg"

    def test_png_with_transparency_does_not_crash(self):
        # Student agar PNG upload kare (transparency ke sath) — JPEG
        # transparency support nahi karta, RGB conversion crash nahi
        # honi chahiye
        png_with_alpha = _make_test_image(500, 400, mode="RGBA", color=(0, 255, 0, 128))
        jpeg_bytes, mime_type = resize_image_for_upload(png_with_alpha)

        result_img = Image.open(io.BytesIO(jpeg_bytes))
        assert result_img.mode == "RGB"  # alpha channel drop ho gaya, crash nahi hua

    def test_exactly_at_max_width_is_not_resized(self):
        # Boundary case: width == max_width bilkul — resize trigger nahi
        # hona chahiye (width > max_width hi condition hai, >= nahi)
        exact = _make_test_image(1600, 900)
        jpeg_bytes, mime_type = resize_image_for_upload(exact, max_width=1600)

        result_img = Image.open(io.BytesIO(jpeg_bytes))
        assert result_img.width == 1600
        assert result_img.height == 900