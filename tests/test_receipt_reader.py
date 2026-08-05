"""receipt_reader のユニットテスト(API呼び出しはモック)"""

import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from utils import receipt_reader


def _make_image_bytes(width, height, fmt="JPEG"):
    """テスト用のダミー画像を生成する"""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class TestShrinkImage:
    def test_large_image_is_resized_to_max_long_edge(self):
        data = _make_image_bytes(2200, 1100)
        shrunk = receipt_reader._shrink_image(data)
        img = Image.open(io.BytesIO(shrunk))
        assert max(img.size) == receipt_reader.MAX_LONG_EDGE
        # アスペクト比維持
        assert img.size == (1100, 550)

    def test_small_image_is_not_upscaled(self):
        data = _make_image_bytes(400, 300)
        shrunk = receipt_reader._shrink_image(data)
        img = Image.open(io.BytesIO(shrunk))
        assert img.size == (400, 300)

    def test_output_is_jpeg(self):
        data = _make_image_bytes(400, 300, fmt="PNG")
        shrunk = receipt_reader._shrink_image(data)
        img = Image.open(io.BytesIO(shrunk))
        assert img.format == "JPEG"

    def test_broken_bytes_raise_receipt_read_error(self):
        with pytest.raises(receipt_reader.ReceiptReadError):
            receipt_reader._shrink_image(b"not an image")
