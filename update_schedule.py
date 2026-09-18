from datetime import date

from database import sync_schedule_from


if __name__ == "__main__":
    result = sync_schedule_from(date(2026, 9, 18))
    print("SCHEDULE_UPDATE_OK", result)