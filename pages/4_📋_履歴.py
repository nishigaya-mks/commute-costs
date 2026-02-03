"""履歴一覧"""

import streamlit as st
import pandas as pd
from datetime import date, datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import data_store, calculator, styles

st.set_page_config(
    page_title="履歴 - 通勤費管理",
    page_icon="📋",
    layout="wide",
)

# モバイル対応CSS適用
styles.apply_mobile_styles()

st.title("📋 履歴一覧")

tab1, tab2, tab3 = st.tabs(["月別収支", "ETC履歴", "給油記録"])

# --- 月別収支 ---
with tab1:
    st.header("月別収支")

    today = date.today()
    history = calculator.get_monthly_balance_history(24)

    if history:
        # データがある月のみ表示
        valid_history = [
            h for h in history
            if h['allowance'] > 0 or h['etc_total'] > 0 or h['fuel_amount'] > 0
        ]

        if valid_history:
            df = pd.DataFrame(valid_history)
            df = df[["year_month", "allowance", "etc_total", "fuel_amount", "balance", "commute_days", "fuel_efficiency"]]
            df.columns = ["年月", "支給額", "高速代", "ガソリン代", "差額", "通勤日数", "燃費"]

            # スタイリング
            def style_balance(val):
                if pd.isna(val):
                    return ""
                color = "green" if val >= 0 else "red"
                return f"color: {color}"

            styled_df = df.style.applymap(style_balance, subset=["差額"])

            st.dataframe(
                styled_df,
                use_container_width=True,
                column_config={
                    "支給額": st.column_config.NumberColumn(format="¥%d"),
                    "高速代": st.column_config.NumberColumn(format="¥%d"),
                    "ガソリン代": st.column_config.NumberColumn(format="¥%d"),
                    "差額": st.column_config.NumberColumn(format="¥%d"),
                    "燃費": st.column_config.NumberColumn(format="%.1f km/L"),
                },
            )

            # 年間合計
            st.subheader(f"{today.year}年 累計")
            current_year_data = [h for h in valid_history if h['year_month'].startswith(str(today.year))]
            if current_year_data:
                total_allowance = sum(h['allowance'] for h in current_year_data)
                total_etc = sum(h['etc_total'] for h in current_year_data)
                total_fuel = sum(h['fuel_amount'] for h in current_year_data)
                total_balance = total_allowance - total_etc - total_fuel

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("累計支給", f"¥{total_allowance:,}")
                with col2:
                    st.metric("累計高速代", f"¥{total_etc:,}")
                with col3:
                    st.metric("累計ガソリン代", f"¥{total_fuel:,}")
                with col4:
                    st.metric("累計差額", f"¥{total_balance:,}")
        else:
            st.info("データがありません")
    else:
        st.info("データがありません")

# --- ETC履歴 ---
with tab2:
    st.header("ETC利用履歴")

    today = date.today()

    col1, col2 = st.columns(2)
    with col1:
        year = st.selectbox(
            "年",
            options=list(range(today.year, today.year - 3, -1)),
            key="etc_year",
        )
    with col2:
        month = st.selectbox(
            "月",
            options=list(range(1, 13)),
            index=today.month - 1,
            key="etc_month",
        )

    records = data_store.get_etc_records_for_month(year, month)

    if records:
        st.write(f"{len(records)}件")

        df = pd.DataFrame(records)
        df_display = df[["entry_datetime", "entry_ic", "exit_ic", "toll_fee", "actual_payment", "discount_type"]]
        df_display.columns = ["入口日時", "入口IC", "出口IC", "通行料金", "支払額", "割引"]

        st.dataframe(
            df_display,
            use_container_width=True,
            column_config={
                "通行料金": st.column_config.NumberColumn(format="¥%d"),
                "支払額": st.column_config.NumberColumn(format="¥%d"),
            },
        )

        # 月合計
        total_toll = sum(r["toll_fee"] for r in records)
        total_payment = sum(r["actual_payment"] for r in records)
        unique_days = len({datetime.fromisoformat(r["entry_datetime"]).date() for r in records})

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("通行料金合計", f"¥{total_toll:,}")
        with col2:
            st.metric("支払額合計", f"¥{total_payment:,}")
        with col3:
            st.metric("通勤日数", f"{unique_days}日")
    else:
        st.info(f"{year}年{month}月のETC履歴はありません")

# --- 給油記録 ---
with tab3:
    st.header("給油記録")

    refueling_data = data_store.load_refueling()
    records = refueling_data.get("records", [])

    if records:
        sorted_records = sorted(records, key=lambda x: x["date"], reverse=True)

        df = pd.DataFrame(sorted_records)
        df_display = df[["date", "odometer", "liters", "amount", "fuel_efficiency"]]
        df_display.columns = ["日付", "オドメーター", "給油量", "金額", "燃費"]

        st.dataframe(
            df_display,
            use_container_width=True,
            column_config={
                "オドメーター": st.column_config.NumberColumn(format="%d km"),
                "給油量": st.column_config.NumberColumn(format="%.1f L"),
                "金額": st.column_config.NumberColumn(format="¥%d"),
                "燃費": st.column_config.NumberColumn(format="%.1f km/L"),
            },
        )

        # 統計
        total_liters = sum(r["liters"] for r in records)
        total_amount = sum(r["amount"] for r in records)
        efficiencies = [r["fuel_efficiency"] for r in records if r.get("fuel_efficiency")]
        avg_efficiency = sum(efficiencies) / len(efficiencies) if efficiencies else 0

        st.subheader("累計")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("総給油量", f"{total_liters:.1f} L")
        with col2:
            st.metric("総額", f"¥{total_amount:,}")
        with col3:
            st.metric("平均燃費", f"{avg_efficiency:.1f} km/L")
    else:
        st.info("給油記録がありません")
