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

    # 年月選択
    col1, col2 = st.columns(2)
    with col1:
        balance_year = st.selectbox(
            "年",
            options=list(range(today.year, today.year - 3, -1)),
            key="balance_year",
        )
    with col2:
        balance_month = st.selectbox(
            "月",
            options=["-"] + list(range(1, 13)),
            index=today.month,  # "-"が0番目なので、今月は index=month
            key="balance_month",
        )

    # 選択月のデータを取得
    history = calculator.get_monthly_balance_history(24)

    if history:
        if balance_month == "-":
            # 年間合計
            year_data = [h for h in history if h['year_month'].startswith(str(balance_year))
                        and (h['allowance'] > 0 or h['etc_total'] > 0 or h['fuel_amount'] > 0)]
            if year_data:
                st.write(f"**{balance_year}年 合計**")
                total_allowance = sum(h['allowance'] for h in year_data)
                total_etc = sum(h['etc_total'] for h in year_data)
                total_fuel = sum(h['fuel_amount'] for h in year_data)
                total_balance = total_allowance - total_etc - total_fuel
                total_days = sum(h['commute_days'] for h in year_data)
                efficiencies = [h['fuel_efficiency'] for h in year_data if h.get('fuel_efficiency')]
                avg_efficiency = sum(efficiencies) / len(efficiencies) if efficiencies else 0

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("支給額", f"¥{total_allowance:,}")
                with col2:
                    st.metric("高速代", f"¥{total_etc:,}")
                with col3:
                    st.metric("ガソリン代", f"¥{total_fuel:,}")
                with col4:
                    st.metric("差額", f"¥{total_balance:,}")

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("通勤日数", f"{total_days}日")
                with col2:
                    if avg_efficiency > 0:
                        st.metric("平均燃費", f"{avg_efficiency:.1f} km/L")
                    else:
                        st.metric("平均燃費", "---")
            else:
                st.info(f"{balance_year}年のデータはありません")
        else:
            # 月別データ
            selected_ym = f"{balance_year}-{balance_month:02d}"
            month_data = next((h for h in history if h['year_month'] == selected_ym), None)

            if month_data and (month_data['allowance'] > 0 or month_data['etc_total'] > 0 or month_data['fuel_amount'] > 0):
                st.write(f"**{balance_year}年{balance_month}月**")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("支給額", f"¥{month_data['allowance']:,}")
                with col2:
                    st.metric("高速代", f"¥{month_data['etc_total']:,}")
                with col3:
                    st.metric("ガソリン代", f"¥{month_data['fuel_amount']:,}")
                with col4:
                    balance_color = "normal" if month_data['balance'] >= 0 else "inverse"
                    st.metric("差額", f"¥{month_data['balance']:,}", delta_color=balance_color)

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("通勤日数", f"{month_data['commute_days']}日")
                with col2:
                    if month_data.get('fuel_efficiency'):
                        st.metric("燃費", f"{month_data['fuel_efficiency']:.1f} km/L")
                    else:
                        st.metric("燃費", "---")
            else:
                st.info(f"{balance_year}年{balance_month}月のデータはありません")

        # 履歴テーブル
        st.divider()
        st.subheader("履歴一覧")

        valid_history = [
            h for h in history
            if h['allowance'] > 0 or h['etc_total'] > 0 or h['fuel_amount'] > 0
        ]

        if valid_history:
            df = pd.DataFrame(valid_history)
            df = df[["year_month", "allowance", "etc_total", "fuel_amount", "balance", "commute_days", "fuel_efficiency"]]
            df.columns = ["年月", "支給額", "高速代", "ガソリン代", "差額", "通勤日数", "燃費"]

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

            # 累計表示
            st.divider()
            st.subheader("累計")
            period_option = st.radio(
                "期間",
                ["今月", "今年", "すべて"],
                horizontal=True,
                key="balance_period"
            )

            if period_option == "今月":
                current_ym = f"{today.year}-{today.month:02d}"
                filter_data = [h for h in valid_history if h['year_month'] == current_ym]
                period_label = f"{today.year}年{today.month}月"
            elif period_option == "今年":
                filter_data = [h for h in valid_history if h['year_month'].startswith(str(today.year))]
                period_label = f"{today.year}年"
            else:
                filter_data = valid_history
                period_label = "全期間"

            if filter_data:
                total_allowance = sum(h['allowance'] for h in filter_data)
                total_etc = sum(h['etc_total'] for h in filter_data)
                total_fuel = sum(h['fuel_amount'] for h in filter_data)
                total_balance = total_allowance - total_etc - total_fuel

                st.caption(f"📅 {period_label}")
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
                st.info(f"{period_label}のデータがありません")
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
        etc_year = st.selectbox(
            "年",
            options=list(range(today.year, today.year - 3, -1)),
            key="etc_year",
        )
    with col2:
        etc_month = st.selectbox(
            "月",
            options=["-"] + list(range(1, 13)),
            index=today.month,
            key="etc_month",
        )

    # データ取得
    all_etc = data_store.load_etc_history().get("records", [])

    if etc_month == "-":
        # 年間データ
        records = [r for r in all_etc if r["entry_datetime"].startswith(str(etc_year))]
        period_label = f"{etc_year}年"
    else:
        # 月別データ
        selected_ym = f"{etc_year}-{etc_month:02d}"
        records = [r for r in all_etc if r["entry_datetime"].startswith(selected_ym)]
        period_label = f"{etc_year}年{etc_month}月"

    if records:
        # 日時でソート
        records = sorted(records, key=lambda x: x["entry_datetime"], reverse=True)
        st.write(f"**{period_label}** {len(records)}件")

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

        # 合計
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
        st.info(f"{period_label}のETC履歴はありません")

    # 累計表示
    st.divider()
    st.subheader("累計")
    etc_period = st.radio(
        "期間",
        ["今月", "今年", "すべて"],
        horizontal=True,
        key="etc_period"
    )

    all_etc = data_store.load_etc_history().get("records", [])
    if all_etc:
        if etc_period == "今月":
            current_ym = f"{today.year}-{today.month:02d}"
            filter_etc = [r for r in all_etc if r["entry_datetime"].startswith(current_ym)]
            period_label = f"{today.year}年{today.month}月"
        elif etc_period == "今年":
            filter_etc = [r for r in all_etc if r["entry_datetime"].startswith(str(today.year))]
            period_label = f"{today.year}年"
        else:
            filter_etc = all_etc
            period_label = "全期間"

        if filter_etc:
            etc_total_toll = sum(r["toll_fee"] for r in filter_etc)
            etc_total_payment = sum(r["actual_payment"] for r in filter_etc)
            etc_unique_days = len({datetime.fromisoformat(r["entry_datetime"]).date() for r in filter_etc})

            st.caption(f"📅 {period_label}")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("累計通行料金", f"¥{etc_total_toll:,}")
            with col2:
                st.metric("累計支払額", f"¥{etc_total_payment:,}")
            with col3:
                st.metric("累計通勤日数", f"{etc_unique_days}日")
        else:
            st.info(f"{period_label}のデータがありません")
    else:
        st.info("ETC履歴がありません")

# --- 給油記録 ---
with tab3:
    st.header("給油記録")

    today = date.today()

    # 年月選択
    col1, col2 = st.columns(2)
    with col1:
        fuel_year = st.selectbox(
            "年",
            options=list(range(today.year, today.year - 3, -1)),
            key="fuel_year",
        )
    with col2:
        fuel_month = st.selectbox(
            "月",
            options=["-"] + list(range(1, 13)),
            index=today.month,
            key="fuel_month",
        )

    refueling_data = data_store.load_refueling()
    all_records = refueling_data.get("records", [])

    # distance未計算のレコードがあれば再計算で補完
    if all_records and any("distance" not in r for r in all_records):
        all_records = data_store.recalculate_fuel_efficiency(all_records)

    # データをフィルタ
    if fuel_month == "-":
        # 年間データ
        filtered_records = [r for r in all_records if r["date"].startswith(str(fuel_year))]
        period_label = f"{fuel_year}年"
    else:
        # 月別データ
        selected_ym = f"{fuel_year}-{fuel_month:02d}"
        filtered_records = [r for r in all_records if r["date"].startswith(selected_ym)]
        period_label = f"{fuel_year}年{fuel_month}月"

    if filtered_records:
        sorted_records = sorted(filtered_records, key=lambda x: x["date"], reverse=True)
        st.write(f"**{period_label}** {len(sorted_records)}件")

        df = pd.DataFrame(sorted_records)
        df_display = df[["date", "odometer", "liters", "amount", "distance", "fuel_efficiency"]]
        df_display.columns = ["日付", "オドメーター", "給油量", "金額", "走行距離", "燃費"]

        st.dataframe(
            df_display,
            use_container_width=True,
            column_config={
                "オドメーター": st.column_config.NumberColumn(format="%d km"),
                "給油量": st.column_config.NumberColumn(format="%.1f L"),
                "金額": st.column_config.NumberColumn(format="¥%d"),
                "走行距離": st.column_config.NumberColumn(format="%d km"),
                "燃費": st.column_config.NumberColumn(format="%.1f km/L"),
            },
        )

        # 合計
        total_liters = sum(r["liters"] for r in filtered_records)
        total_amount = sum(r["amount"] for r in filtered_records)
        total_distance = sum(r["distance"] for r in filtered_records if r.get("distance"))
        efficiencies = [r["fuel_efficiency"] for r in filtered_records if r.get("fuel_efficiency")]
        avg_efficiency = sum(efficiencies) / len(efficiencies) if efficiencies else 0

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("給油量合計", f"{total_liters:.1f} L")
        with col2:
            st.metric("金額合計", f"¥{total_amount:,}")
        with col3:
            st.metric("走行距離合計", f"{total_distance:,} km" if total_distance else "---")
        with col4:
            if avg_efficiency > 0:
                st.metric("平均燃費", f"{avg_efficiency:.1f} km/L")
            else:
                st.metric("平均燃費", "---")
    else:
        st.info(f"{period_label}の給油記録はありません")

    # 累計表示
    st.divider()
    st.subheader("累計")
    fuel_period = st.radio(
        "期間",
        ["今月", "今年", "すべて"],
        horizontal=True,
        key="fuel_period"
    )

    if all_records:
        if fuel_period == "今月":
            current_ym = f"{today.year}-{today.month:02d}"
            filter_fuel = [r for r in all_records if r["date"].startswith(current_ym)]
            period_label = f"{today.year}年{today.month}月"
        elif fuel_period == "今年":
            filter_fuel = [r for r in all_records if r["date"].startswith(str(today.year))]
            period_label = f"{today.year}年"
        else:
            filter_fuel = all_records
            period_label = "全期間"

        if filter_fuel:
            total_liters = sum(r["liters"] for r in filter_fuel)
            total_amount = sum(r["amount"] for r in filter_fuel)
            total_distance = sum(r["distance"] for r in filter_fuel if r.get("distance"))
            efficiencies = [r["fuel_efficiency"] for r in filter_fuel if r.get("fuel_efficiency")]
            avg_efficiency = sum(efficiencies) / len(efficiencies) if efficiencies else 0

            st.caption(f"📅 {period_label}")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("総給油量", f"{total_liters:.1f} L")
            with col2:
                st.metric("総額", f"¥{total_amount:,}")
            with col3:
                st.metric("総走行距離", f"{total_distance:,} km" if total_distance else "---")
            with col4:
                st.metric("平均燃費", f"{avg_efficiency:.1f} km/L")
        else:
            st.info(f"{period_label}のデータがありません")
    else:
        st.info("給油記録がありません")
