import os
from datetime import date, timedelta, datetime
from supabase import create_client, Client

# Load Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Needs service_role key
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

TODAY = date.today()
YEAR_END = date(TODAY.year, 12, 31)

def get_all_users():
    response = supabase.table("users").select("id").execute()
    return response.data or []

def get_holidays(user_id):
    response = supabase.table("saved_holidays").select("date").eq("user_id", user_id).execute()
    return {datetime.fromisoformat(item["date"]).date() for item in response.data or []}

def get_time_off(user_id):
    response = supabase.table("time_off").select("type, allowed").eq("user_id", user_id).execute()
    return {item["type"]: item["allowed"] for item in response.data or []}

def generate_candidate_windows(start_day, holidays):
    days_to_check = [0, 1, 2]
    windows = []
    for offset in days_to_check:
        end_day = start_day + timedelta(days=2 + offset)
        range_days = (end_day - start_day).days + 1
        days_off_needed = sum(
            1 for i in range(range_days)
            if (start_day + timedelta(days=i)).weekday() not in [5, 6]
            and (start_day + timedelta(days=i)) not in holidays
        )
        if days_off_needed <= offset:
            windows.append({
                "start": start_day,
                "end": end_day,
                "days_off_needed": days_off_needed
            })
    return windows

def window_already_exists(user_id, startdate, enddate):
    response = supabase.table("windows").select("id") \
        .eq("user_id", user_id) \
        .eq("startdate", startdate.isoformat()) \
        .eq("enddate", enddate.isoformat()) \
        .execute()
    return len(response.data or []) > 0

def generate_and_insert_windows(user_id, holidays, time_off):
    used_time_off = 0
    windows_added = 0

    current = TODAY
    while current <= YEAR_END:
        if current.weekday() == 4:
            candidates = generate_candidate_windows(current, holidays)
            for window in candidates:
                if used_time_off + window["days_off_needed"] > sum(time_off.values()):
                    continue
                if window_already_exists(user_id, window["start"], window["end"]):
                    continue
                supabase.table("windows").insert({
                    "user_id": user_id,
                    "startdate": window["start"].isoformat(),
                    "enddate": window["end"].isoformat()
                }).execute()
                used_time_off += window["days_off_needed"]
                windows_added += 1
        current += timedelta(days=1)

    print(f"Generated {windows_added} windows for user {user_id}")

def main():
    users = get_all_users()
    for user in users:
        user_id = user["id"]
        holidays = get_holidays(user_id)
        time_off = get_time_off(user_id)
        generate_and_insert_windows(user_id, holidays, time_off)

if __name__ == "__main__":
    main()
