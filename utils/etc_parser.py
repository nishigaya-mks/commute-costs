"""ETC CSV パーサー: ETC利用照会サービスのCSVを解析する"""

import io
from datetime import datetime, timedelta
from pathlib import Path


def excel_serial_to_date(serial: float) -> datetime:
    """
    Excelシリアル値を日付に変換する

    Excelの日付は1900年1月1日を1とするシリアル値
    （ただし1900年2月29日のバグがあるため、1899-12-30が基準）
    """
    excel_epoch = datetime(1899, 12, 30)
    return excel_epoch + timedelta(days=int(serial))


def excel_time_to_time(time_fraction: float) -> tuple[int, int]:
    """
    Excelの時刻小数を時分に変換する

    1日 = 1.0 として、0.5 = 12:00, 0.25 = 6:00 など
    """
    total_minutes = int(time_fraction * 24 * 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return hours, minutes


def parse_date_ymd(date_str: str) -> datetime:
    """
    YY/MM/DD 形式の日付をパースする
    """
    parts = date_str.strip().split("/")
    if len(parts) == 3:
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        # 2桁年を4桁に変換（25 -> 2025）
        if year < 100:
            year += 2000
        return datetime(year, month, day)
    raise ValueError(f"Invalid date format: {date_str}")


def parse_time_hm(time_str: str) -> tuple[int, int]:
    """
    HH:MM 形式の時刻をパースする
    """
    parts = time_str.strip().split(":")
    if len(parts) >= 2:
        return int(parts[0]), int(parts[1])
    raise ValueError(f"Invalid time format: {time_str}")


def parse_discount_type(notes: str) -> str:
    """備考欄から割引種別を抽出する"""
    if not notes:
        return ""
    if "朝夕" in notes:
        return "朝夕"
    if "深夜" in notes:
        return "深夜"
    if "休日" in notes:
        return "休日"
    return ""


def detect_format(first_data_line: str) -> tuple[str, bool]:
    """
    CSVのフォーマットを検出する

    Returns:
        tuple[str, bool]: (区切り文字, Excel形式かどうか)
    """
    # 区切り文字を検出
    if "\t" in first_data_line:
        delimiter = "\t"
    else:
        delimiter = ","

    cols = first_data_line.split(delimiter)

    # 最初の列がExcelシリアル値（数値）か日付文字列かで判定
    try:
        float(cols[0])
        is_excel_format = True
    except ValueError:
        is_excel_format = False

    return delimiter, is_excel_format


def parse_etc_csv(file_content: bytes | str, encoding: str = "cp932") -> list[dict]:
    """
    ETC CSVファイルをパースしてレコードのリストを返す

    対応フォーマット:
    - ETC利用照会サービス直接ダウンロード（カンマ区切り、YY/MM/DD形式）
    - Excel経由エクスポート（タブ区切り、シリアル値形式）

    Args:
        file_content: CSVファイルの内容（バイト列または文字列）
        encoding: ファイルのエンコーディング（デフォルト: cp932）

    Returns:
        list[dict]: パース結果のレコードリスト
    """
    # バイト列の場合はデコード
    if isinstance(file_content, bytes):
        text = file_content.decode(encoding)
    else:
        text = file_content

    lines = text.strip().replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(lines) < 2:
        return []

    # ヘッダー行をスキップ、データ行を取得
    data_lines = [l for l in lines[1:] if l.strip()]
    if not data_lines:
        return []

    # フォーマット検出
    delimiter, is_excel_format = detect_format(data_lines[0])

    records = []
    for line in data_lines:
        line = line.strip()
        if not line:
            continue

        cols = line.split(delimiter)
        if len(cols) < 11:
            continue

        try:
            if is_excel_format:
                # Excel形式: シリアル値
                entry_date = excel_serial_to_date(float(cols[0]))
                entry_hour, entry_min = excel_time_to_time(float(cols[1]))
                entry_datetime = entry_date.replace(hour=entry_hour, minute=entry_min)

                exit_date = excel_serial_to_date(float(cols[2]))
                exit_hour, exit_min = excel_time_to_time(float(cols[3]))
                exit_datetime = exit_date.replace(hour=exit_hour, minute=exit_min)
            else:
                # 直接ダウンロード形式: YY/MM/DD, HH:MM
                entry_date = parse_date_ymd(cols[0])
                entry_hour, entry_min = parse_time_hm(cols[1])
                entry_datetime = entry_date.replace(hour=entry_hour, minute=entry_min)

                exit_date = parse_date_ymd(cols[2])
                exit_hour, exit_min = parse_time_hm(cols[3])
                exit_datetime = exit_date.replace(hour=exit_hour, minute=exit_min)

            # 料金の取得
            toll_fee = int(cols[8]) if cols[8] else 0
            actual_payment = int(cols[10]) if cols[10] else 0

            # 備考から割引種別を抽出
            notes = cols[14] if len(cols) > 14 else ""
            discount_type = parse_discount_type(notes)

            record = {
                "entry_datetime": entry_datetime.isoformat(),
                "exit_datetime": exit_datetime.isoformat(),
                "entry_ic": cols[4].strip(),
                "exit_ic": cols[5].strip(),
                "toll_fee": toll_fee,
                "actual_payment": actual_payment,
                "discount_type": discount_type,
            }
            records.append(record)

        except (ValueError, IndexError) as e:
            # パースエラーは無視して次の行へ
            continue

    return records


def parse_etc_csv_file(filepath: str | Path, encoding: str = "cp932") -> list[dict]:
    """
    ETC CSVファイルを読み込んでパースする

    Args:
        filepath: CSVファイルのパス
        encoding: ファイルのエンコーディング

    Returns:
        list[dict]: パース結果のレコードリスト
    """
    filepath = Path(filepath)
    with open(filepath, "rb") as f:
        content = f.read()
    return parse_etc_csv(content, encoding)


def summarize_etc_records(records: list[dict]) -> dict:
    """
    ETCレコードのサマリーを作成する

    Returns:
        dict: {
            "total_records": レコード数,
            "total_toll": 合計料金,
            "total_payment": 実際の支払い合計,
            "unique_days": ユニークな日数,
            "date_range": (最初の日, 最後の日)
        }
    """
    if not records:
        return {
            "total_records": 0,
            "total_toll": 0,
            "total_payment": 0,
            "unique_days": 0,
            "date_range": None,
        }

    dates = []
    for r in records:
        dt = datetime.fromisoformat(r["entry_datetime"])
        dates.append(dt.date())

    unique_dates = set(dates)

    return {
        "total_records": len(records),
        "total_toll": sum(r["toll_fee"] for r in records),
        "total_payment": sum(r["actual_payment"] for r in records),
        "unique_days": len(unique_dates),
        "date_range": (min(dates), max(dates)) if dates else None,
    }
