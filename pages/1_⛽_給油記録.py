"""給油記録入力"""

import streamlit as st
from datetime import date, datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import data_store, styles

st.set_page_config(
    page_title="給油記録 - 通勤費管理",
    page_icon="⛽",
)

# モバイル対応CSS適用
styles.apply_mobile_styles()

st.title("⛽ 給油記録")

# 設定から給油所リストを取得
settings = data_store.load_settings()
gas_stations = settings.get("gas_stations", [])

# 前回の給油記録を取得（デフォルト値用）
last_record = data_store.get_last_refueling_record()

st.header("新規給油記録")

with st.form("refueling_form"):
    # 給油日
    refuel_date = st.date_input(
        "給油日",
        value=date.today(),
    )

    # 給油所選択
    if gas_stations:
        # 前回の給油所をデフォルトに
        default_index = 0
        if last_record and last_record.get("station"):
            try:
                default_index = gas_stations.index(last_record["station"])
            except ValueError:
                default_index = 0

        station = st.selectbox(
            "給油所",
            options=gas_stations,
            index=default_index,
        )
    else:
        station = st.text_input(
            "給油所",
            value="",
            help="設定画面で給油所を登録すると選択できます",
        )

    # 数値入力を2列で表示
    col1, col2 = st.columns(2)

    with col1:
        liters = st.number_input(
            "給油量 (L)",
            min_value=0.0,
            value=35.0,
            step=0.5,
            format="%.1f",
        )

    with col2:
        amount = st.number_input(
            "金額 (円)",
            min_value=0,
            value=5000,
            step=100,
        )

    # 単価プレビュー
    if liters > 0 and amount > 0:
        unit_price = amount / liters
        st.success(f"💰 単価: ¥{unit_price:.1f}/L")

    # オドメーター
    odometer = st.number_input(
        "オドメーター (km)",
        min_value=0,
        value=last_record["odometer"] + 500 if last_record else 0,
        step=1,
        help="現在の総走行距離",
    )

    submitted = st.form_submit_button("✅ 登録", type="primary", use_container_width=True)

    if submitted:
        if odometer <= 0:
            st.error("オドメーターを入力してください")
        elif liters <= 0:
            st.error("給油量を入力してください")
        elif amount <= 0:
            st.error("金額を入力してください")
        else:
            record = {
                "date": refuel_date.isoformat(),
                "odometer": odometer,
                "liters": liters,
                "amount": amount,
                "station": station if station else None,
                "unit_price": round(amount / liters, 1),
            }
            record_id = data_store.add_refueling_record(record)
            st.success("✅ 給油記録を登録しました")
            st.rerun()

# 前回の記録を表示
if last_record:
    st.divider()
    st.subheader("前回の給油記録")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("日付", last_record["date"])
        if last_record.get("fuel_efficiency"):
            st.metric("燃費", f"{last_record['fuel_efficiency']} km/L")
    with col2:
        st.metric("オドメーター", f"{last_record['odometer']:,} km")
        if last_record.get("unit_price"):
            st.metric("単価", f"¥{last_record['unit_price']:.1f}/L")

# 直近の給油記録一覧
st.divider()
st.subheader("直近の給油記録")

refueling_data = data_store.load_refueling()
records = refueling_data.get("records", [])

if records:
    # 日付の新しい順にソート
    sorted_records = sorted(records, key=lambda x: x["date"], reverse=True)[:5]

    for record in sorted_records:
        # 単価を計算
        unit_price = record.get("unit_price")
        if not unit_price and record.get("liters") and record.get("amount"):
            unit_price = record["amount"] / record["liters"]

        # カード形式で表示（モバイルフレンドリー）
        with st.container():
            station_name = record.get("station", "")
            st.markdown(f"**📅 {record['date']}** {station_name}")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.caption(f"⛽ {record['liters']:.1f} L")
            with col2:
                st.caption(f"💰 ¥{record['amount']:,}")
            with col3:
                if record.get("fuel_efficiency"):
                    st.caption(f"📊 {record['fuel_efficiency']} km/L")

            st.markdown("---")
else:
    st.info("給油記録がありません")

# 給油所未登録の場合の案内
if not gas_stations:
    st.warning("⚙️ 設定画面で給油所を登録すると、選択できるようになります。")
