"""レシート撮影用のブラウザ内カメラコンポーネント。

st.camera_input はインカメラ固定・プレビューが小さいため、
アウトカメラ既定・全幅プレビューの自前コンポーネントで置き換える。
"""

import base64
from pathlib import Path

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).parent / "receipt_camera_component"

_component = components.declare_component("receipt_camera", path=str(_COMPONENT_DIR))


def receipt_camera(key=None):
    """カメラを表示し、撮影済みならJPEGバイト列を返す（未撮影は None）。"""
    data_url = _component(key=key, default=None)
    if not data_url:
        return None
    try:
        return base64.b64decode(data_url.split(",", 1)[1])
    except Exception:
        return None
