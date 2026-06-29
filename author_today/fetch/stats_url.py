from __future__ import annotations

from datetime import date, datetime, time
from urllib.parse import urlencode

STATS_BASE = "https://author.today/report/work/stats"


def build_stats_url(
    book_id: int,
    period_start: date,
    period_end: date,
    value_type: str = "hit",
) -> str:
    """Собрать URL страницы статистики прочтений."""
    start_dt = datetime.combine(period_start, time(20, 0))
    end_dt = datetime.combine(period_end, time(19, 59, 59))
    params = {
        "startDate": start_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "endDate": end_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "workId": book_id,
        "valueType": value_type,
    }
    return f"{STATS_BASE}?{urlencode(params)}"


def parse_period_from_url(url: str) -> tuple[date | None, date | None]:
    """Извлечь даты периода из URL (заготовка для будущего)."""
    # TODO: разбор query startDate/endDate
    return None, None
