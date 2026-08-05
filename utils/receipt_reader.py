"""レシート画像から給油情報を抽出する(Claude API Vision)"""

import base64
import io
import json
from datetime import datetime

import anthropic
import streamlit as st
from PIL import Image, ImageOps

MODEL = "claude-haiku-4-5"
MAX_LONG_EDGE = 1100
JPEG_QUALITY = 85
AMOUNT_TOLERANCE = 0.02


class ReceiptReadError(Exception):
    """レシート読み取り失敗"""


def _shrink_image(image_bytes: bytes) -> bytes:
    """画像を長辺 MAX_LONG_EDGE px 以内の JPEG に縮小する(トークン節約)"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        raise ReceiptReadError("画像を開けませんでした") from e
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    w, h = img.size
    long_edge = max(w, h)
    if long_edge > MAX_LONG_EDGE:
        scale = MAX_LONG_EDGE / long_edge
        img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()


def _check_consistency(result: dict) -> dict:
    """給油量×単価と金額の乖離が AMOUNT_TOLERANCE を超えたら warning を付ける"""
    liters = result.get("liters")
    unit_price = result.get("unit_price")
    amount = result.get("amount")
    if liters and unit_price and amount:
        if abs(liters * unit_price - amount) / abs(amount) > AMOUNT_TOLERANCE:
            result["warning"] = True
    return result


def _validate_date(value: str | None) -> str | None:
    """YYYY-MM-DD 形式に解釈できれば正規化して返し、それ以外は None を返す"""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _get_api_key() -> str | None:
    """st.secrets から API キーを取得する。未設定なら None"""
    try:
        return st.secrets["anthropic"]["api_key"]
    except (KeyError, FileNotFoundError):
        return None


def is_available() -> bool:
    """レシート読み取り機能が使える状態か(API キー設定済みか)"""
    return bool(_get_api_key())


RECEIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {
            "type": ["string", "null"],
            "description": "給油日を YYYY-MM-DD 形式で。和暦・短縮表記は変換する",
        },
        "station": {"type": ["string", "null"], "description": "給油所名"},
        "liters": {"type": ["number", "null"], "description": "給油量(リットル)"},
        "unit_price": {"type": ["number", "null"], "description": "単価(円/L)"},
        "amount": {"type": ["integer", "null"], "description": "支払金額合計(円、税込)"},
    },
    "required": ["date", "station", "liters", "unit_price", "amount"],
    "additionalProperties": False,
}


def _build_prompt(gas_stations: list) -> str:
    station_note = "レシート記載の店名を返してください。"
    if gas_stations:
        station_note = (
            "次のリストに該当するものがあれば必ずリスト内の表記そのままで返してください: "
            + "、".join(gas_stations)
            + "。該当がなければレシート記載の店名を返してください。"
        )
    return (
        "これはガソリンスタンドのレシートの写真です。以下の項目を抽出してください。\n"
        "- date: 給油日(YYYY-MM-DD 形式に変換)\n"
        "- station: 給油所名。" + station_note + "\n"
        "- liters: 給油量(リットル)\n"
        "- unit_price: ガソリン単価(円/L)\n"
        "- amount: 支払金額合計(円、税込)\n"
        "読み取れない項目は null にしてください。"
        "ガソリンスタンドのレシートではない画像の場合は全項目 null にしてください。"
    )


def extract_receipt(image_bytes: bytes, gas_stations: list) -> dict:
    """レシート画像から給油情報を抽出する。

    Returns:
        {"date", "station", "liters", "unit_price", "amount"} の dict。
        不明項目は None。金額整合性が疑わしい場合は "warning": True 付き。
    Raises:
        ReceiptReadError: API キー未設定・API エラー・読み取り不能時
    """
    api_key = _get_api_key()
    if not api_key:
        raise ReceiptReadError("APIキーが設定されていません")

    image_data = base64.standard_b64encode(_shrink_image(image_bytes)).decode("utf-8")
    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            output_config={"format": {"type": "json_schema", "schema": RECEIPT_SCHEMA}},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": _build_prompt(gas_stations)},
                    ],
                }
            ],
        )
    except anthropic.APIError as e:
        raise ReceiptReadError(f"API呼び出しに失敗しました({e.__class__.__name__})") from e

    if response.stop_reason == "refusal":
        raise ReceiptReadError("読み取りが拒否されました")

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise ReceiptReadError("応答が空でした")
    try:
        result = json.loads(text)
    except json.JSONDecodeError as e:
        raise ReceiptReadError("応答の解析に失敗しました") from e

    result["date"] = _validate_date(result.get("date"))
    if all(result.get(k) is None for k in ("date", "station", "liters", "unit_price", "amount")):
        raise ReceiptReadError("レシートとして読み取れませんでした")
    return _check_consistency(result)
