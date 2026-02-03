"""共通スタイル: モバイル対応CSS"""

import streamlit as st

MOBILE_CSS = """
<style>
/* モバイル対応 (768px以下) */
@media (max-width: 768px) {
    /* メインコンテンツの余白調整 */
    .main .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
        padding-top: 1rem;
    }

    /* メトリクスを縦並びに */
    [data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }

    /* ボタンを大きく */
    .stButton > button {
        width: 100%;
        padding: 0.75rem 1rem;
        font-size: 1.1rem;
    }

    /* 入力フィールドを大きく */
    .stNumberInput input,
    .stTextInput input,
    .stSelectbox select {
        font-size: 16px !important;  /* iOS のズーム防止 */
        padding: 0.75rem;
    }

    /* サイドバーを非表示（トグルで表示） */
    [data-testid="stSidebar"] {
        min-width: 0;
    }

    /* タイトルのサイズ調整 */
    h1 {
        font-size: 1.5rem !important;
    }

    h2 {
        font-size: 1.25rem !important;
    }

    /* グラフの高さ調整 */
    .js-plotly-plot {
        height: 300px !important;
    }
}

/* タブレット対応 (768px - 1024px) */
@media (min-width: 769px) and (max-width: 1024px) {
    .main .block-container {
        padding-left: 2rem;
        padding-right: 2rem;
    }
}

/* 共通スタイル */
.stButton > button[kind="primary"] {
    background-color: #2ecc71;
    border: none;
}

.stButton > button[kind="primary"]:hover {
    background-color: #27ae60;
}

/* メトリクスカードの調整 */
[data-testid="stMetricValue"] {
    font-size: 1.5rem;
}

/* フォーム内の余白調整 */
.stForm {
    padding: 1rem;
    border-radius: 0.5rem;
    background-color: #f8f9fa;
}
</style>
"""


def apply_mobile_styles():
    """モバイル対応CSSを適用する"""
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)


def is_mobile() -> bool:
    """
    モバイルデバイスかどうかを判定する（簡易版）

    注意: Streamlitではサーバーサイドで正確な判定は難しいため、
    CSSメディアクエリで対応するのが主な手段
    """
    # Streamlitではクライアント情報の取得が限られているため、
    # 基本的にはCSSで対応
    return False
