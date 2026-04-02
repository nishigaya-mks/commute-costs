"""収支・燃費計算ロジック"""

from __future__ import annotations

from datetime import date
from . import data_store


def calculate_monthly_balance(year: int, month: int) -> dict:
    """
    指定月の収支を計算する

    Returns:
        dict: {
            "year_month": "YYYY-MM",
            "allowance": 支給額,
            "etc_total": 高速代合計,
            "fuel_amount": ガソリン代,
            "balance": 差額,
            "commute_days": 通勤日数（参考）,
            "fuel_efficiency": 燃費（あれば）,
            "source": データソース
        }
    """
    year_month = f"{year:04d}-{month:02d}"

    # 支給額（設定から取得）
    allowance = data_store.get_allowance_for_month(year, month)

    # ETC利用料金
    etc_total = data_store.get_etc_total_for_month(year, month)

    # 通勤日数（参考情報）
    commute_days = data_store.get_commute_days_for_month(year, month)

    # ガソリン代: 月次データがあればそれを使用、なければ給油記録から集計
    monthly_record = data_store.get_monthly_record(year, month)

    if monthly_record and monthly_record.get("source") == "manual":
        # 手動入力の月次データを使用
        fuel_amount = monthly_record.get("fuel_amount", 0)
        fuel_efficiency = monthly_record.get("fuel_efficiency")
        source = "manual"
    else:
        # 給油記録から集計
        fuel_amount = data_store.get_fuel_total_for_month(year, month)
        fuel_efficiency = calculate_monthly_fuel_efficiency(year, month)
        source = "refueling"

    # 走行距離（給油記録から）
    refueling_records = data_store.get_refueling_records_for_month(year, month)
    total_distance = sum(r["distance"] for r in refueling_records if r.get("distance"))

    # 収支計算
    balance = allowance - etc_total - fuel_amount

    # キロ単価（ガソリン代 ÷ 走行距離）
    cost_per_km = round(fuel_amount / total_distance, 1) if total_distance > 0 and fuel_amount > 0 else None

    return {
        "year_month": year_month,
        "allowance": allowance,
        "etc_total": etc_total,
        "fuel_amount": fuel_amount,
        "balance": balance,
        "commute_days": commute_days,
        "fuel_efficiency": fuel_efficiency,
        "total_distance": total_distance,
        "cost_per_km": cost_per_km,
        "source": source,
    }


def calculate_monthly_fuel_efficiency(year: int, month: int) -> float | None:
    """
    指定月の平均燃費を計算する（給油記録から）

    Returns:
        float | None: 燃費 (km/L)、計算不可の場合はNone
    """
    records = data_store.get_refueling_records_for_month(year, month)

    efficiencies = [r["fuel_efficiency"] for r in records if r.get("fuel_efficiency")]

    if not efficiencies:
        return None

    return round(sum(efficiencies) / len(efficiencies), 2)


def calculate_year_to_date_balance(year: int, up_to_month: int) -> dict:
    """
    年初から指定月までの累計収支を計算する

    Returns:
        dict: {
            "year": 年,
            "months": 月数,
            "total_allowance": 累計支給額,
            "total_etc": 累計高速代,
            "total_fuel": 累計ガソリン代,
            "total_balance": 累計差額,
            "monthly_data": 月別データのリスト
        }
    """
    monthly_data = []
    total_allowance = 0
    total_etc = 0
    total_fuel = 0

    for month in range(1, up_to_month + 1):
        data = calculate_monthly_balance(year, month)
        monthly_data.append(data)
        total_allowance += data["allowance"]
        total_etc += data["etc_total"]
        total_fuel += data["fuel_amount"]

    total_balance = total_allowance - total_etc - total_fuel

    return {
        "year": year,
        "months": up_to_month,
        "total_allowance": total_allowance,
        "total_etc": total_etc,
        "total_fuel": total_fuel,
        "total_balance": total_balance,
        "monthly_data": monthly_data,
    }


def get_fuel_efficiency_trend(limit: int = 12) -> list[dict]:
    """
    燃費推移を取得する（直近N件）

    Returns:
        list[dict]: [{
            "date": 日付,
            "fuel_efficiency": 燃費
        }, ...]
    """
    data = data_store.load_refueling()
    records = data.get("records", [])

    # 燃費データがあるレコードのみ抽出
    with_efficiency = [
        {"date": r["date"], "fuel_efficiency": r["fuel_efficiency"]}
        for r in records
        if r.get("fuel_efficiency")
    ]

    # 日付順にソートして直近N件を取得
    sorted_records = sorted(with_efficiency, key=lambda x: x["date"], reverse=True)
    return sorted_records[:limit][::-1]  # 古い順に並べ直す


def get_monthly_balance_history(months: int = 12) -> list[dict]:
    """
    月別収支履歴を取得する（直近N ヶ月）

    Returns:
        list[dict]: 月別収支データのリスト
    """
    today = date.today()
    result = []

    for i in range(months - 1, -1, -1):
        # i ヶ月前の年月を計算
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1

        data = calculate_monthly_balance(year, month)
        result.append(data)

    return result


def get_fuel_efficiency_ranking() -> list[dict]:
    """
    燃費ランキング（良い順）を返す

    Returns:
        list[dict]: [{"date": 日付, "fuel_efficiency": 燃費, "rank": 順位}, ...]
    """
    data = data_store.load_refueling()
    records = data.get("records", [])

    with_efficiency = [
        {"date": r["date"], "fuel_efficiency": r["fuel_efficiency"], "station": r.get("station", "")}
        for r in records
        if r.get("fuel_efficiency")
    ]

    sorted_records = sorted(with_efficiency, key=lambda x: x["fuel_efficiency"], reverse=True)
    for i, r in enumerate(sorted_records):
        r["rank"] = i + 1

    return sorted_records


def get_fuel_efficiency_rank(efficiency: float) -> tuple[int, int]:
    """
    指定した燃費の順位を返す

    Returns:
        tuple[int, int]: (順位, 総数)
    """
    ranking = get_fuel_efficiency_ranking()
    total = len(ranking)
    if total == 0:
        return (1, 1)

    rank = 1
    for r in ranking:
        if r["fuel_efficiency"] > efficiency:
            rank += 1
        else:
            break

    return (rank, total)


def get_monthly_balance_ranking() -> list[dict]:
    """
    月別差額ランキング（黒字順）を返す（データがある月のみ）

    Returns:
        list[dict]: [{"year_month": 年月, "balance": 差額, "rank": 順位}, ...]
    """
    history = get_monthly_balance_history(24)
    valid = [
        {"year_month": h["year_month"], "balance": h["balance"]}
        for h in history
        if h["allowance"] > 0 or h["etc_total"] > 0 or h["fuel_amount"] > 0
    ]

    sorted_data = sorted(valid, key=lambda x: x["balance"], reverse=True)
    for i, r in enumerate(sorted_data):
        r["rank"] = i + 1

    return sorted_data


def get_monthly_balance_rank(year_month: str) -> tuple[int, int] | None:
    """
    指定月の差額の順位を返す

    Returns:
        tuple[int, int] | None: (順位, 総数) or None
    """
    ranking = get_monthly_balance_ranking()
    if not ranking:
        return None

    for r in ranking:
        if r["year_month"] == year_month:
            return (r["rank"], len(ranking))

    return None
