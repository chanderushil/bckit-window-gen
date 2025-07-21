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
    response = supabase.table("saved_holidays").select("date").eq("user_id", user_id).execute()
    return {datetime.fromisoformat(item["date"]).date() for item in response.data or []}

def get_time_off(user_id):
    response = supabase.table("time_off").select("type, allowed").eq("user_id", user_id).execute()
    return {item["type"]: item["allowed"] for item in response.data or []}

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

    used_time_off = 0
    windows_added = 0
    current = TODAY

    while current <= YEAR_END:
        if current.weekday() == 4:  # Friday
            candidates = generate_candidate_windows(current, holidays)
            for window in candidates:
                if used_time_off + window["days_off_needed"] > sum(time_off.values()):
                    continue
                supabase.table("windows").insert({
                    "user_id": user_id,
                    "startdate": window["start"].isoformat(),
                    "enddate": window["end"].isoformat()
                }).execute()
                used_time_off += window["days_off_needed"]
                windows_added += 1
        current += timedelta(days=1)

    print(f"✅ Generated {windows_added} windows for user {user_id}")

def main():
    users = get_all_users()
    for user in users:
        user_id = user["id"]
        holidays = get_holidays(user_id)
        time_off = get_time_off(user_id)
        generate_and_insert_windows(user_id, holidays, time_off)

if __name__ == "__main__":
    main()
