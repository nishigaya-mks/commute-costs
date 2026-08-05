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

    def test_exif_orientation_is_applied(self):
        # orientation=6 (90度回転) 付きの横長画像 → 縦長に変換されること
        img = Image.new("RGB", (600, 400), color=(255, 255, 255))
        exif = Image.Exif()
        exif[274] = 6  # Orientation: Rotate 90 CW
        buf = io.BytesIO()
        img.save(buf, format="JPEG", exif=exif)
        shrunk = receipt_reader._shrink_image(buf.getvalue())
        out = Image.open(io.BytesIO(shrunk))
        assert out.size == (400, 600)


class TestCheckConsistency:
    def test_consistent_values_no_warning(self):
        result = {"liters": 35.0, "unit_price": 160.0, "amount": 5600}
        out = receipt_reader._check_consistency(result)
        assert "warning" not in out

    def test_inconsistent_values_set_warning(self):
        # 35.0 * 160.0 = 5600 に対し 7000 は ±2% を超える
        result = {"liters": 35.0, "unit_price": 160.0, "amount": 7000}
        out = receipt_reader._check_consistency(result)
        assert out["warning"] is True

    def test_missing_values_skip_check(self):
        result = {"liters": None, "unit_price": 160.0, "amount": 5600}
        out = receipt_reader._check_consistency(result)
        assert "warning" not in out

    def test_negative_amount_sets_warning(self):
        result = {"liters": 35.0, "unit_price": 160.0, "amount": -5600}
        out = receipt_reader._check_consistency(result)
        assert out["warning"] is True


class TestValidateDate:
    def test_valid_iso_date_passes(self):
        assert receipt_reader._validate_date("2026-08-06") == "2026-08-06"

    def test_invalid_date_returns_none(self):
        assert receipt_reader._validate_date("2026/08/06") is None
        assert receipt_reader._validate_date("令和8年8月6日") is None

    def test_none_returns_none(self):
        assert receipt_reader._validate_date(None) is None

    def test_non_padded_date_is_normalized(self):
        assert receipt_reader._validate_date("2026-8-6") == "2026-08-06"


class TestIsAvailable:
    def test_available_when_key_exists(self, monkeypatch):
        monkeypatch.setattr(receipt_reader, "_get_api_key", lambda: "sk-ant-xxx")
        assert receipt_reader.is_available() is True

    def test_unavailable_when_key_missing(self, monkeypatch):
        monkeypatch.setattr(receipt_reader, "_get_api_key", lambda: None)
        assert receipt_reader.is_available() is False
