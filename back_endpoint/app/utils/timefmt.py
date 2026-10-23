"""时间格式化工具。"""

from datetime import date, datetime, timedelta

DT_FMT = "%Y-%m-%d %H:%M:%S"
D_FMT = "%Y-%m-%d"


def now() -> datetime:
    return datetime.now().replace(microsecond=0)


def today() -> date:
    return date.today()


def fmt_dt(value: datetime | None) -> str | None:
    return value.strftime(DT_FMT) if value else None


def fmt_d(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime(D_FMT)
    return value.strftime(D_FMT)


def parse_date(value: str) -> date:
    """严格 yyyy-MM-dd，非法抛 ValueError（调用方转 40001）。"""
    if len(value) != 10:
        raise ValueError(value)
    return datetime.strptime(value, D_FMT).date()


def day_start(value: str) -> datetime:
    return datetime.combine(parse_date(value), datetime.min.time())


def day_after(value: str) -> datetime:
    return day_start(value) + timedelta(days=1)


def reltime(value: datetime | None) -> str:
    if not value:
        return ""
    delta = datetime.now() - value
    seconds = delta.total_seconds()
    if seconds < 60:
        return "刚刚"
    if seconds < 3600:
        return f"{int(seconds // 60)} 分钟前"
    if seconds < 86400:
        return f"{int(seconds // 3600)} 小时前"
    if seconds < 86400 * 2:
        return "昨天"
    if seconds < 86400 * 7:
        return f"{int(seconds // 86400)} 天前"
    return value.strftime(D_FMT)


def month_start() -> datetime:
    n = datetime.now()
    return datetime(n.year, n.month, 1)


def money(value) -> float:
    """Decimal → 2 位小数 float。"""
    if value is None:
        return 0.0
    return float(round(float(value), 2))
