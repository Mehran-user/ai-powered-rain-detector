import csv
import logging
import os
from datetime import datetime, timedelta

from utils.format import parse_datetime

logger = logging.getLogger("rain_logger")

FIELDS = [
    "timestamp",
    "status",
    "rain_type",
    "rain_confidence",
    "rain_type_confidence",
    "message",
    "warnings",
    "image_path",
    "raw_image_path",
]

STATUS_POWER_OFF = "POWER_OFF"


class CsvLogger:
    def __init__(self, path):
        self.path = path
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(FIELDS)
            logger.info("Database created: %s", path)

    def append(self, row):
        record = {field: row.get(field, "") or "" for field in FIELDS}
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writerow(record)
        logger.info("Database entry added for %s.", record["timestamp"])

    def read_records(self):
        records = []
        with open(self.path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(row)
        return records

    def existing_timestamps(self):
        return {row["timestamp"] for row in self.read_records()}

    def last_timestamp(self):
        latest = None
        for row in self.read_records():
            timestamp = parse_datetime(row["timestamp"])
            if timestamp and (latest is None or timestamp > latest):
                latest = timestamp
        return latest

    def backfill_power_off(self, schedule_start, interval_minutes, now):
        existing = self.existing_timestamps()
        last = self.last_timestamp()
        if last is None:
            logger.info("No previous records; skipping POWER_OFF backfill.")
            return 0
        interval = timedelta(minutes=interval_minutes)
        start_n = int((last - schedule_start).total_seconds() // (interval_minutes * 60)) + 1
        count = 0
        n = start_n
        while True:
            slot = schedule_start + n * interval
            if slot > now:
                break
            timestamp = slot.strftime("%Y-%m-%d %H:%M:%S")
            if slot > last and timestamp not in existing:
                self.append(
                    {
                        "timestamp": timestamp,
                        "status": STATUS_POWER_OFF,
                        "rain_type": "",
                        "rain_confidence": "",
                        "rain_type_confidence": "",
                        "message": "",
                        "warnings": "",
                        "image_path": "",
                        "raw_image_path": "",
                    }
                )
                count += 1
            n += 1
        if count:
            logger.info("Backfilled %d missing capture(s) as POWER_OFF.", count)
        return count
