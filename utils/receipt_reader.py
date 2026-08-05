"""レシート画像から給油情報を抽出する(Claude API Vision)"""

import io

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
