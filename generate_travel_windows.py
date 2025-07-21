import os
from datetime import date, timedelta, datetime
from supabase import create_client, Client

# Load Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # service_role key
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

TODAY = date.today()
YEAR_END = date(TODAY.year, 12, 31)

def get_all_users():
    response = supabase.table("users").select("id").execute()
    return response.data or []

def get_holidays(user_id):
    response = (
        supabase.table("saved_holidays")
        .select("holiday_id, holidays(date)")
        .eq("user_id", user_id)
        .execute()
    )

    return {
        datetime.fromisoformat(item["holidays"]["date"]).date()
        for item in response.data or []
        if "holidays" in item and item["holidays"].get("date")
    }

def get_time_off(user_id):
    response = (
        supabase.table("time_off")
        .select("type, qty")
        .eq("user_id", user_id)
        .execute()
    )
    return {item["type"]: item["qty"] for item in response.data or []}

def user_has_windows(user_id):
    response = supabase.table("windows").select("id").eq("user_id", user_id).limit(1).execute()
    return len(response.data or []) > 0

def generate_candidate_windows(start_day, holidays):
    days_to_check = [0, 1, 2]
    windows = []
    for offset in days_to_check:
        end_day = start_day + timedelta(days=2 + offset)
        range_days = (end_day - start_day).days + 1
        days_off_needed = sum(
            1 for i in range(range_days)
            if (start_day + timedelta(days=i)).weekday() not in [5, 6]  # Not Sat/Sun
            and (start_day + timedelta(days=i)) not in holidays
        )
        if days_off_needed <= offset:
            windows.append({
                "start": start_day,
                "end": end_day,
                "days_off_needed": days_off_needed
            })
    return windows

def generate_and_insert_windows(user_id, holidays, time_off):
    if user_has_windows(user_id):
        print(f"Skipping user {user_id}: already has travel windows")
        return

    total_pto_available = sum(time_off.values())
    used_time_off = 0
    long_trip_count = 0
    max_long_trips = 2
    max_windows = 3
    windows_added = 0
    used_dates = set()
    current = TODAY

    while current <= YEAR_END and windows_added < max_windows:
        if current.weekday() == 4:  # Friday
            candidates = generate_candidate_windows(current, holidays)
            # Sort by descending length (prefer longer trips first)
            candidates.sort(key=lambda x: (x["end"] - x["start"]).days + 1, reverse=True)
            for window in candidates:
                total_days = (window["end"] - window["start"]).days + 1
                pto_days = window["days_off_needed"]

                if total_days < 4:
                    continue
                if pto_days > 5:
                    continue
                if pto_days > 3 and long_trip_count >= max_long_trips:
                    continue
                if used_time_off + pto_days > total_pto_available:
                    continue

                window_range = {window["start"] + timedelta(days=i) for i in range(total_days)}
                if used_dates & window_range:
                    continue  # overlaps

                # ✅ Passed all filters, insert
                supabase.table("windows").insert({
                    "user_id": user_id,
                    "startdate": window["start"].isoformat(),
                    "enddate": window["end"].isoformat(),
                    "days_used": pto_days
                }).execute()

                used_dates.update(window_range)
                used_time_off += pto_days
                if pto_days > 3:
                    long_trip_count += 1
                windows_added += 1
                break  # only accept the first viable window for this weekend

        current += timedelta(days=1)

    print(f"✅ {windows_added} travel windows created for user {user_id}")

def main():
    users = get_all_users()
    for user in users:
        user_id = user["id"]
        holidays = get_holidays(user_id)
        time_off = get_time_off(user_id)
        generate_and_insert_windows(user_id, holidays, time_off)

if __name__ == "__main__":
    main()
