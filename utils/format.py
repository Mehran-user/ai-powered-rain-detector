from datetime import datetime


def ordinal(day):
    if 11 <= day % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def capture_label(dt):
    hour = dt.hour % 12 or 12
    period = "AM" if dt.hour < 12 else "PM"
    return f"{ordinal(dt.day)} {dt.strftime('%B')} {dt.year} {hour}:{dt.minute:02d} {period}"


def csv_timestamp(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_datetime(text):
    if not text:
        return None
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
