"""設定"""

import streamlit as st
from datetime import date

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import data_store, styles

st.set_page_config(
    page_title="設定 - 通勤費管理",
    page_icon="⚙️",
)

# モバイル対応CSS適用
styles.apply_mobile_styles()

st.title("⚙️ 設定")

settings = data_store.load_settings()

# --- 支給額設定 ---
st.header("💰 支給額設定")

allowance_history = settings.get("allowance_history", [])

st.subheader("現在の支給額")

if allowance_history:
    current = max(allowance_history, key=lambda x: x["effective_date"])
    st.metric("月額支給額", f"¥{current['amount']:,}")
    st.caption(f"適用開始日: {current['effective_date']}")
else:
    st.warning("支給額が設定されていません")

st.subheader("支給額を変更")

with st.form("allowance_form"):
    col1, col2 = st.columns(2)

    with col1:
        effective_date = st.date_input(
            "適用開始日",
            value=date.today().replace(day=1),
        )

    with col2:
        amount = st.number_input(
            "月額支給額 (円)",
            min_value=0,
            value=current["amount"] if allowance_history else 75000,
            step=1000,
        )

    submitted = st.form_submit_button("登録", type="primary")

    if submitted:
        new_entry = {
            "effective_date": effective_date.isoformat(),
            "amount": amount,
        }

        # 同じ日付のエントリがあれば更新、なければ追加
        updated = False
        for i, entry in enumerate(allowance_history):
            if entry["effective_date"] == new_entry["effective_date"]:
                allowance_history[i] = new_entry
                updated = True
                break

        if not updated:
            allowance_history.append(new_entry)

        settings["allowance_history"] = sorted(allowance_history, key=lambda x: x["effective_date"])
        data_store.save_settings(settings)
        st.success("支給額を更新しました")
        st.rerun()

# 支給額履歴
if allowance_history:
    st.subheader("支給額履歴")
    for entry in sorted(allowance_history, key=lambda x: x["effective_date"], reverse=True):
        st.write(f"- {entry['effective_date']}: ¥{entry['amount']:,}")

st.divider()

# --- IC設定 ---
st.header("🛣️ 通勤ルート設定")

col1, col2 = st.columns(2)

with col1:
    home_ic = st.text_input(
        "自宅側IC",
        value=settings.get("home_ic", ""),
        help="通勤時の入口IC",
    )

with col2:
    work_ic = st.text_input(
        "勤務先側IC",
        value=settings.get("work_ic", ""),
        help="通勤時の出口IC",
    )

if st.button("IC設定を保存"):
    settings["home_ic"] = home_ic
    settings["work_ic"] = work_ic
    data_store.save_settings(settings)
    st.success("IC設定を保存しました")

st.divider()

# --- 給油所設定 ---
st.header("⛽ 給油所設定")

gas_stations = settings.get("gas_stations", [])

st.subheader("登録済みの給油所")

if gas_stations:
    for i, station in enumerate(gas_stations):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"- {station}")
        with col2:
            if st.button("削除", key=f"del_station_{i}"):
                gas_stations.pop(i)
                settings["gas_stations"] = gas_stations
                data_store.save_settings(settings)
                st.rerun()
else:
    st.info("給油所が登録されていません")

st.subheader("給油所を追加")

with st.form("gas_station_form"):
    new_station = st.text_input(
        "給油所名",
        placeholder="例: ENEOS 富浦SS",
    )

    if st.form_submit_button("追加"):
        if new_station and new_station not in gas_stations:
            gas_stations.append(new_station)
            settings["gas_stations"] = gas_stations
            data_store.save_settings(settings)
            st.success(f"「{new_station}」を追加しました")
            st.rerun()
        elif new_station in gas_stations:
            st.warning("この給油所は既に登録されています")
        else:
            st.error("給油所名を入力してください")

st.divider()

# --- データ管理 ---
st.header("📂 データ管理")

st.subheader("データ概要")

etc_data = data_store.load_etc_history()
refueling_data = data_store.load_refueling()
monthly_data = data_store.load_monthly_data()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("ETC履歴", f"{len(etc_data.get('records', []))}件")

with col2:
    st.metric("給油記録", f"{len(refueling_data.get('records', []))}件")

with col3:
    st.metric("月次データ", f"{len(monthly_data.get('months', []))}件")

st.subheader("データファイルの場所")

data_dir = Path(__file__).parent.parent.parent / "data"
st.code(str(data_dir.resolve()))

st.caption("OneDriveで同期する場合は、このディレクトリをOneDrive内に配置してください。")
