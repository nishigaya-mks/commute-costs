"""月次実績入力"""

import streamlit as st
from datetime import date

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import data_store, styles

st.set_page_config(
    page_title="月次実績 - 通勤費管理",
    page_icon="📝",
)

# モバイル対応CSS適用
styles.apply_mobile_styles()

st.title("📝 月次実績入力")

st.info("💡 給油毎の入力を忘れた月に、まとめて実績を入力できます。")

today = date.today()

st.header("月次実績を入力")

with st.form("monthly_form"):
    # 年月選択
    col1, col2 = st.columns(2)
    with col1:
        year = st.number_input(
            "年",
            min_value=2020,
            max_value=2030,
            value=today.year,
        )
    with col2:
        month = st.selectbox(
            "月",
            options=list(range(1, 13)),
            index=today.month - 1,
        )

    st.divider()

    # 走行距離・給油量
    col1, col2 = st.columns(2)
    with col1:
        distance_km = st.number_input(
            "走行距離 (km)",
            min_value=0,
            value=2000,
            step=100,
            help="月間の総走行距離",
        )
    with col2:
        fuel_liters = st.number_input(
            "給油量 (L)",
            min_value=0.0,
            value=90.0,
            step=1.0,
            format="%.1f",
            help="月間の総給油量",
        )

    # ガソリン代
    fuel_amount = st.number_input(
        "ガソリン代合計 (円)",
        min_value=0,
        value=15000,
        step=1000,
    )

    # 燃費プレビュー
    if distance_km > 0 and fuel_liters > 0:
        preview_efficiency = distance_km / fuel_liters
        st.success(f"📊 燃費: {preview_efficiency:.1f} km/L")

    submitted = st.form_submit_button("✅ 登録", type="primary", use_container_width=True)

    if submitted:
        if fuel_amount <= 0:
            st.error("ガソリン代を入力してください")
        else:
            year_month = f"{year:04d}-{month:02d}"

            # 燃費計算
            fuel_efficiency = None
            if distance_km > 0 and fuel_liters > 0:
                fuel_efficiency = round(distance_km / fuel_liters, 2)

            record = {
                "year_month": year_month,
                "source": "manual",
                "distance_km": distance_km,
                "fuel_liters": fuel_liters,
                "fuel_amount": fuel_amount,
                "fuel_efficiency": fuel_efficiency,
            }

            data_store.save_monthly_record(record)
            st.success(f"✅ {year}年{month}月の月次実績を登録しました")
            st.rerun()

# 既存の月次データ一覧
st.divider()
st.subheader("登録済みの月次実績")

monthly_data = data_store.load_monthly_data()
months = monthly_data.get("months", [])

# 手動入力のみ表示
manual_months = [m for m in months if m.get("source") == "manual"]

if manual_months:
    sorted_months = sorted(manual_months, key=lambda x: x["year_month"], reverse=True)

    for m in sorted_months:
        with st.container():
            st.markdown(f"**📅 {m['year_month']}**")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.caption(f"🚗 {m.get('distance_km', 0):,} km")
            with col2:
                st.caption(f"⛽ {m.get('fuel_liters', 0):.1f} L")
            with col3:
                st.caption(f"💰 ¥{m.get('fuel_amount', 0):,}")

            st.markdown("---")
else:
    st.info("手動入力の月次実績はありません")
