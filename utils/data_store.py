"""データストア: Google Sheets版"""

import json
import uuid
import streamlit as st
from datetime import datetime, date
from typing import Any

import gspread
from google.oauth2.service_account import Credentials


# Google Sheets設定
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ワークシート名
WS_SETTINGS = "settings"
WS_ETC_HISTORY = "etc_history"
WS_REFUELING = "refueling"
WS_MONTHLY_DATA = "monthly_data"


@st.cache_resource
def get_gsheet_client():
    """Google Sheets クライアントを取得（キャッシュ）"""
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_resource
def get_spreadsheet():
    """スプレッドシートを取得（キャッシュ）"""
    client = get_gsheet_client()
    spreadsheet_url = st.secrets["spreadsheet"]["url"]
    return client.open_by_url(spreadsheet_url)


def _get_or_create_worksheet(name: str, headers: list[str] | None = None):
    """ワークシートを取得（なければ作成）"""
    spreadsheet = get_spreadsheet()
    try:
        ws = spreadsheet.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=name, rows=1000, cols=20)
        if headers:
            ws.append_row(headers)
    return ws


def clear_cache():
    """キャッシュをクリア"""
    st.cache_data.clear()


def generate_id() -> str:
    """ユニークIDを生成する"""
    return str(uuid.uuid4())


# === 設定 ===

@st.cache_data(ttl=60)
def load_settings() -> dict:
    """設定を読み込む（60秒キャッシュ）"""
    ws = _get_or_create_worksheet(WS_SETTINGS, ["key", "value"])
    records = ws.get_all_records()

    settings = {}
    for row in records:
        key = row.get("key", "")
        value = row.get("value", "")
        if key and value:
            try:
                settings[key] = json.loads(value)
            except json.JSONDecodeError:
                settings[key] = value
    return settings


def save_settings(settings: dict) -> None:
    """設定を保存する"""
    ws = _get_or_create_worksheet(WS_SETTINGS, ["key", "value"])
    ws.clear()
    ws.append_row(["key", "value"])

    for key, value in settings.items():
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value, ensure_ascii=False)
        else:
            value_str = json.dumps(value)
        ws.append_row([key, value_str])

    # キャッシュクリア
    load_settings.clear()


def get_allowance_for_month(year: int, month: int) -> int:
    """指定月の支給額を取得する"""
    settings = load_settings()
    allowance_history = settings.get("allowance_history", [])

    target_date = date(year, month, 1)
    applicable_amount = 0

    for entry in sorted(allowance_history, key=lambda x: x["effective_date"]):
        effective = datetime.strptime(entry["effective_date"], "%Y-%m-%d").date()
        if effective <= target_date:
            applicable_amount = entry["amount"]

    return applicable_amount


# === ETC履歴 ===

ETC_HEADERS = ["id", "entry_datetime", "entry_ic", "exit_datetime", "exit_ic",
               "toll_fee", "actual_payment", "discount_type", "vehicle_type", "route", "status"]


@st.cache_data(ttl=60)
def load_etc_history() -> dict:
    """ETC履歴を読み込む（60秒キャッシュ）"""
    ws = _get_or_create_worksheet(WS_ETC_HISTORY, ETC_HEADERS)
    records = ws.get_all_records()

    # 数値型に変換
    for r in records:
        r["toll_fee"] = int(r.get("toll_fee", 0) or 0)
        r["actual_payment"] = int(r.get("actual_payment", 0) or 0)

    return {"records": records}


def save_etc_history(data: dict) -> None:
    """ETC履歴を保存する"""
    ws = _get_or_create_worksheet(WS_ETC_HISTORY, ETC_HEADERS)
    ws.clear()

    # ヘッダー + 全データを一括で書き込み
    rows = [ETC_HEADERS]
    for record in data.get("records", []):
        row = [record.get(h, "") for h in ETC_HEADERS]
        rows.append(row)

    if rows:
        ws.append_rows(rows, value_input_option='RAW')

    load_etc_history.clear()


def add_etc_records(records: list[dict]) -> tuple[int, int, int]:
    """
    ETC履歴に複数レコードを追加する（重複チェック・確定更新付き）

    Returns:
        tuple[int, int, int]: (追加件数, スキップ件数, 更新件数)
    """
    data = load_etc_history()
    existing = data.get("records", [])

    # 既存レコードをキー→(インデックス, レコード)のマップに
    # キーは入口日時・入口IC・出口ICで判定（料金は変わる可能性があるため含めない）
    existing_map = {}
    for idx, r in enumerate(existing):
        key = (r["entry_datetime"], r["entry_ic"], r["exit_ic"])
        existing_map[key] = idx

    added = 0
    skipped = 0
    updated = 0
    need_save = False

    for record in records:
        key = (record["entry_datetime"], record["entry_ic"], record["exit_ic"])
        new_status = record.get("status", "")

        if key not in existing_map:
            # 新規レコード
            record["id"] = generate_id()
            existing.append(record)
            existing_map[key] = len(existing) - 1
            added += 1
            need_save = True
        else:
            # 既存レコードあり
            idx = existing_map[key]
            existing_status = existing[idx].get("status", "")

            # 確認中 → 確定 の場合のみ更新
            if existing_status != "確定" and new_status == "確定":
                # 既存レコードのIDを維持しつつ、料金情報を更新
                existing[idx]["actual_payment"] = record.get("actual_payment", 0)
                existing[idx]["toll_fee"] = record.get("toll_fee", 0)
                existing[idx]["discount_type"] = record.get("discount_type", "")
                existing[idx]["status"] = "確定"
                updated += 1
                need_save = True
            else:
                skipped += 1

    # 変更があれば全件書き直し
    if need_save:
        save_etc_history({"records": existing})

    return added, skipped, updated


def get_etc_records_for_month(year: int, month: int) -> list[dict]:
    """指定月のETC履歴を取得する"""
    data = load_etc_history()
    records = data.get("records", [])

    result = []
    for r in records:
        entry_dt = datetime.fromisoformat(r["entry_datetime"])
        if entry_dt.year == year and entry_dt.month == month:
            result.append(r)

    return sorted(result, key=lambda x: x["entry_datetime"])


def get_commute_days_for_month(year: int, month: int) -> int:
    """指定月の通勤日数を取得する（ETC利用日数）"""
    records = get_etc_records_for_month(year, month)
    unique_days = {datetime.fromisoformat(r["entry_datetime"]).date() for r in records}
    return len(unique_days)


def get_etc_total_for_month(year: int, month: int) -> int:
    """指定月のETC利用料金合計を取得する"""
    records = get_etc_records_for_month(year, month)
    return sum(r.get("actual_payment", 0) for r in records)


# === 給油記録 ===

REFUEL_HEADERS = ["id", "date", "odometer", "liters", "amount", "station",
                  "unit_price", "fuel_efficiency"]


@st.cache_data(ttl=60)
def load_refueling() -> dict:
    """給油記録を読み込む（60秒キャッシュ）"""
    ws = _get_or_create_worksheet(WS_REFUELING, REFUEL_HEADERS)
    records = ws.get_all_records()

    # 数値型に変換
    for r in records:
        r["odometer"] = int(r.get("odometer", 0) or 0)
        r["liters"] = float(r.get("liters", 0) or 0)
        r["amount"] = int(r.get("amount", 0) or 0)
        r["unit_price"] = float(r.get("unit_price", 0) or 0) if r.get("unit_price") else None
        r["fuel_efficiency"] = float(r.get("fuel_efficiency", 0) or 0) if r.get("fuel_efficiency") else None

    return {"records": records}


def save_refueling(data: dict) -> None:
    """給油記録を保存する"""
    ws = _get_or_create_worksheet(WS_REFUELING, REFUEL_HEADERS)
    ws.clear()
    ws.append_row(REFUEL_HEADERS)

    for record in data.get("records", []):
        row = [record.get(h, "") for h in REFUEL_HEADERS]
        ws.append_row(row)


def add_refueling_record(record: dict) -> str:
    """給油記録を追加する"""
    data = load_refueling()
    records = data.get("records", [])

    record["id"] = generate_id()

    # 燃費計算: 前回の記録があれば計算
    if records:
        prev = max(records, key=lambda x: x["date"])
        if prev["odometer"] < record["odometer"]:
            distance = record["odometer"] - prev["odometer"]
            record["fuel_efficiency"] = round(distance / record["liters"], 2)

    # 直接シートに追加
    ws = _get_or_create_worksheet(WS_REFUELING, REFUEL_HEADERS)
    row = [record.get(h, "") for h in REFUEL_HEADERS]
    ws.append_row(row)
    load_refueling.clear()

    return record["id"]


def get_refueling_records_for_month(year: int, month: int) -> list[dict]:
    """指定月の給油記録を取得する"""
    data = load_refueling()
    records = data.get("records", [])

    result = []
    for r in records:
        record_date = datetime.strptime(r["date"], "%Y-%m-%d").date()
        if record_date.year == year and record_date.month == month:
            result.append(r)

    return sorted(result, key=lambda x: x["date"])


def get_fuel_total_for_month(year: int, month: int) -> int:
    """指定月のガソリン代合計を取得する（給油記録から）"""
    records = get_refueling_records_for_month(year, month)
    return sum(r.get("amount", 0) for r in records)


def get_last_refueling_record() -> dict | None:
    """最新の給油記録を取得する"""
    data = load_refueling()
    records = data.get("records", [])
    if not records:
        return None
    return max(records, key=lambda x: x["date"])


# === 月次データ ===

MONTHLY_HEADERS = ["year_month", "source", "distance_km", "fuel_liters",
                   "fuel_amount", "fuel_efficiency"]


@st.cache_data(ttl=60)
def load_monthly_data() -> dict:
    """月次データを読み込む（60秒キャッシュ）"""
    ws = _get_or_create_worksheet(WS_MONTHLY_DATA, MONTHLY_HEADERS)
    records = ws.get_all_records()

    # 数値型に変換
    for r in records:
        r["distance_km"] = int(r.get("distance_km", 0) or 0)
        r["fuel_liters"] = float(r.get("fuel_liters", 0) or 0)
        r["fuel_amount"] = int(r.get("fuel_amount", 0) or 0)
        r["fuel_efficiency"] = float(r.get("fuel_efficiency", 0) or 0) if r.get("fuel_efficiency") else None

    return {"months": records}


def save_monthly_data(data: dict) -> None:
    """月次データを保存する"""
    ws = _get_or_create_worksheet(WS_MONTHLY_DATA, MONTHLY_HEADERS)
    ws.clear()
    ws.append_row(MONTHLY_HEADERS)

    for record in data.get("months", []):
        row = [record.get(h, "") for h in MONTHLY_HEADERS]
        ws.append_row(row)

    load_monthly_data.clear()


def get_monthly_record(year: int, month: int) -> dict | None:
    """指定月の月次データを取得する"""
    data = load_monthly_data()
    year_month = f"{year:04d}-{month:02d}"

    for m in data.get("months", []):
        if m["year_month"] == year_month:
            return m
    return None


def save_monthly_record(record: dict) -> None:
    """月次データを保存する（既存があれば更新）"""
    data = load_monthly_data()
    months = data.get("months", [])

    year_month = record["year_month"]

    # 既存レコードを検索
    for i, m in enumerate(months):
        if m["year_month"] == year_month:
            months[i] = record
            data["months"] = months
            save_monthly_data(data)
            return

    # 新規追加
    ws = _get_or_create_worksheet(WS_MONTHLY_DATA, MONTHLY_HEADERS)
    row = [record.get(h, "") for h in MONTHLY_HEADERS]
    ws.append_row(row)
    load_monthly_data.clear()
