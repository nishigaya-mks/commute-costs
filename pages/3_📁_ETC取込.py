"""ETC履歴取込"""

import streamlit as st
import pandas as pd

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import data_store, etc_parser, styles

st.set_page_config(
    page_title="ETC取込 - 通勤費管理",
    page_icon="📁",
)

# モバイル対応CSS適用
styles.apply_mobile_styles()

st.title("📁 ETC履歴取込")

st.warning("💻 この機能はPCでの利用を推奨します。")

st.markdown("""
ETC利用照会サービスからダウンロードしたCSVファイルをアップロードしてください。

**対応フォーマット:**
- カンマ区切り or タブ区切りCSV
- エンコーディング: Shift-JIS または UTF-8
""")

# ファイルアップロード
uploaded_file = st.file_uploader(
    "CSVファイルを選択",
    type=["csv", "txt"],
    help="ETC利用照会サービスからダウンロードしたCSVファイル",
)

if uploaded_file is not None:
    # ファイル内容を読み込み
    content = uploaded_file.read()

    # エンコーディングを自動判定してパース
    records = None
    last_error = None
    for encoding in ["cp932", "utf-8", "shift_jis"]:
        try:
            records = etc_parser.parse_etc_csv(content, encoding)
            if records:
                break
        except Exception as e:
            last_error = f"{encoding}: {str(e)}"
            continue

    if not records:
        st.error("CSVファイルの解析に失敗しました。フォーマットを確認してください。")

        # デバッグ情報
        with st.expander("デバッグ情報"):
            st.write(f"ファイルサイズ: {len(content)} bytes")
            st.write(f"最後のエラー: {last_error}")

            # 先頭部分をプレビュー
            try:
                preview = content[:500].decode('cp932', errors='replace')
                st.code(preview, language=None)
            except:
                st.write("プレビューを表示できません")
    else:
        # サマリーを表示
        summary = etc_parser.summarize_etc_records(records)

        st.success(f"{summary['total_records']}件のレコードを検出しました")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("通行料金合計", f"¥{summary['total_toll']:,}")
        with col2:
            st.metric("実際の支払い", f"¥{summary['total_payment']:,}")
        with col3:
            st.metric("通勤日数", f"{summary['unique_days']}日")

        if summary['date_range']:
            st.caption(f"期間: {summary['date_range'][0]} 〜 {summary['date_range'][1]}")

        # プレビュー表示
        st.subheader("プレビュー")

        df = pd.DataFrame(records)
        df_display = df[["entry_datetime", "entry_ic", "exit_ic", "toll_fee", "actual_payment", "discount_type"]]
        df_display.columns = ["入口日時", "入口IC", "出口IC", "通行料金", "支払額", "割引"]

        st.dataframe(df_display, use_container_width=True, height=300)

        # 取込ボタン
        if st.button("取り込む", type="primary", use_container_width=True):
            added, skipped = data_store.add_etc_records(records)

            if added > 0:
                st.success(f"{added}件のレコードを取り込みました")
            if skipped > 0:
                st.info(f"{skipped}件は重複のためスキップしました")

            st.balloons()

# 取込済みデータの確認
st.divider()
st.subheader("取込済みデータ")

etc_data = data_store.load_etc_history()
etc_records = etc_data.get("records", [])

if etc_records:
    st.write(f"合計 {len(etc_records)} 件のETC履歴があります")

    # 月別集計
    from collections import defaultdict
    from datetime import datetime

    monthly_stats = defaultdict(lambda: {"count": 0, "total": 0, "days": set()})

    for r in etc_records:
        dt = datetime.fromisoformat(r["entry_datetime"])
        key = f"{dt.year:04d}-{dt.month:02d}"
        monthly_stats[key]["count"] += 1
        monthly_stats[key]["total"] += r.get("actual_payment", 0)
        monthly_stats[key]["days"].add(dt.date())

    # 表示
    st.write("**月別集計:**")
    for ym in sorted(monthly_stats.keys(), reverse=True)[:6]:
        stats = monthly_stats[ym]
        st.write(f"- {ym}: {stats['count']}件, ¥{stats['total']:,}, {len(stats['days'])}日")
else:
    st.info("ETC履歴がありません")
