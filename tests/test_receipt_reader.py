"""receipt_reader のユニットテスト(API呼び出しはモック)"""

import io
import json
from types import SimpleNamespace

import anthropic
import httpx
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


def _fake_client_factory(payload=None, stop_reason="end_turn", raise_error=None, content=None):
    """anthropic.Anthropic を差し替えるフェイク。

    - payload: JSON エンコードして単一テキストブロックとして返す
    - content: 指定時は payload より優先し、content リストをそのまま返す
      (空リストや不正テキストのテスト用)
    - raise_error: 指定時は create() 呼び出し時にその例外を送出する
    - FakeClient.captured_kwargs に create() へ渡された kwargs を記録する
    """

    class FakeMessages:
        def create(self, **kwargs):
            FakeClient.captured_kwargs = kwargs
            if raise_error is not None:
                raise raise_error
            if content is not None:
                resp_content = content
            else:
                resp_content = [SimpleNamespace(type="text", text=json.dumps(payload))]
            return SimpleNamespace(stop_reason=stop_reason, content=resp_content)

    class FakeClient:
        captured_kwargs = None

        def __init__(self, api_key=None):
            self.messages = FakeMessages()

    return FakeClient


GOOD_PAYLOAD = {
    "date": "2026-08-06",
    "station": "ENEOS",
    "liters": 35.5,
    "unit_price": 160.0,
    "amount": 5680,
}


class TestExtractReceipt:
    @pytest.fixture(autouse=True)
    def _api_key(self, monkeypatch):
        monkeypatch.setattr(receipt_reader, "_get_api_key", lambda: "sk-ant-xxx")

    def test_success_returns_parsed_dict(self, monkeypatch):
        monkeypatch.setattr(
            receipt_reader.anthropic, "Anthropic", _fake_client_factory(GOOD_PAYLOAD)
        )
        result = receipt_reader.extract_receipt(
            _make_image_bytes(800, 600), ["ENEOS", "出光"]
        )
        assert result["date"] == "2026-08-06"
        assert result["station"] == "ENEOS"
        assert result["liters"] == 35.5
        assert result["amount"] == 5680
        assert "warning" not in result

    def test_invalid_date_becomes_none(self, monkeypatch):
        payload = dict(GOOD_PAYLOAD, date="26/08/06")
        monkeypatch.setattr(
            receipt_reader.anthropic, "Anthropic", _fake_client_factory(payload)
        )
        result = receipt_reader.extract_receipt(_make_image_bytes(800, 600), [])
        assert result["date"] is None

    def test_all_null_raises(self, monkeypatch):
        payload = {k: None for k in GOOD_PAYLOAD}
        monkeypatch.setattr(
            receipt_reader.anthropic, "Anthropic", _fake_client_factory(payload)
        )
        with pytest.raises(receipt_reader.ReceiptReadError):
            receipt_reader.extract_receipt(_make_image_bytes(800, 600), [])

    def test_inconsistent_amount_sets_warning(self, monkeypatch):
        payload = dict(GOOD_PAYLOAD, amount=9999)
        monkeypatch.setattr(
            receipt_reader.anthropic, "Anthropic", _fake_client_factory(payload)
        )
        result = receipt_reader.extract_receipt(_make_image_bytes(800, 600), [])
        assert result["warning"] is True

    def test_refusal_raises(self, monkeypatch):
        monkeypatch.setattr(
            receipt_reader.anthropic,
            "Anthropic",
            _fake_client_factory(GOOD_PAYLOAD, stop_reason="refusal"),
        )
        with pytest.raises(receipt_reader.ReceiptReadError):
            receipt_reader.extract_receipt(_make_image_bytes(800, 600), [])

    def test_no_api_key_raises(self, monkeypatch):
        monkeypatch.setattr(receipt_reader, "_get_api_key", lambda: None)
        with pytest.raises(receipt_reader.ReceiptReadError):
            receipt_reader.extract_receipt(_make_image_bytes(800, 600), [])

    def test_api_error_raises_receipt_read_error(self, monkeypatch):
        error = anthropic.APIConnectionError(
            request=httpx.Request("POST", "https://api.anthropic.com")
        )
        monkeypatch.setattr(
            receipt_reader.anthropic,
            "Anthropic",
            _fake_client_factory(raise_error=error),
        )
        with pytest.raises(receipt_reader.ReceiptReadError):
            receipt_reader.extract_receipt(_make_image_bytes(800, 600), [])

    def test_empty_content_raises(self, monkeypatch):
        monkeypatch.setattr(
            receipt_reader.anthropic,
            "Anthropic",
            _fake_client_factory(content=[]),
        )
        with pytest.raises(receipt_reader.ReceiptReadError):
            receipt_reader.extract_receipt(_make_image_bytes(800, 600), [])

    def test_invalid_json_raises(self, monkeypatch):
        monkeypatch.setattr(
            receipt_reader.anthropic,
            "Anthropic",
            _fake_client_factory(content=[SimpleNamespace(type="text", text="not json")]),
        )
        with pytest.raises(receipt_reader.ReceiptReadError):
            receipt_reader.extract_receipt(_make_image_bytes(800, 600), [])

    def test_non_dict_json_raises(self, monkeypatch):
        monkeypatch.setattr(
            receipt_reader.anthropic,
            "Anthropic",
            _fake_client_factory(payload=[1, 2]),
        )
        with pytest.raises(receipt_reader.ReceiptReadError):
            receipt_reader.extract_receipt(_make_image_bytes(800, 600), [])

    def test_request_shape(self, monkeypatch):
        fake_cls = _fake_client_factory(GOOD_PAYLOAD)
        monkeypatch.setattr(receipt_reader.anthropic, "Anthropic", fake_cls)
        receipt_reader.extract_receipt(_make_image_bytes(800, 600), ["ENEOS", "出光"])
        kwargs = fake_cls.captured_kwargs
        assert kwargs["model"] == receipt_reader.MODEL
        assert kwargs["output_config"]["format"]["type"] == "json_schema"
        assert kwargs["output_config"]["format"]["schema"] is receipt_reader.RECEIPT_SCHEMA
        content = kwargs["messages"][0]["content"]
        assert content[0]["type"] == "image"
        assert content[0]["source"]["media_type"] == "image/jpeg"
        prompt = content[1]["text"]
        assert "ENEOS" in prompt and "出光" in prompt


class TestBuildPrompt:
    def test_empty_gas_stations_no_list_wording(self):
        prompt = receipt_reader._build_prompt([])
        assert "リスト" not in prompt

    def test_with_gas_stations_includes_names_and_list_wording(self):
        prompt = receipt_reader._build_prompt(["ENEOS", "出光"])
        assert "ENEOS" in prompt
        assert "出光" in prompt
        assert "リスト" in prompt
