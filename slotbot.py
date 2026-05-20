import requests
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import os
import json

# ─────────────────────────────────────────
#  KONFIGURATION – hier alles anpassen
# ─────────────────────────────────────────

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

VENUES = [
    {
        "name": "PadelCity München Tucherpark",
        "type": "playtomic",
        "tenant_id": "ea2bccb9-ea75-486c-959f-921a65df4f32",
        "booking_url": "https://playtomic.io/padelcity-mnchen-tucherpark/ea2bccb9-ea75-486c-959f-921a65df4f32",
    },
    {
        "name": "Sport Insel Taufkirchen",
        "type": "eversports",
        "facility_id": 25080,
        "court_id": 68894,
        "booking_url": "https://www.eversports.de/sb/sport-insel-taufkirchen",
    },
]

DESIRED_TIMES = ["16:30", "17:00", "17:30", "18:00", "18:30", "19:00"]
DURATION_MINUTES = 60
DAYS_AHEAD = 14
STATS_FILE = "stats.json"

# ─────────────────────────────────────────
#  PLAYTOMIC API
# ─────────────────────────────────────────

PLAYTOMIC_API = "https://api.playtomic.io/v1/availability"
PLAYTOMIC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15",
    "Accept": "application/json",
    "X-Requested-With": "com.playtomic.app",
}

def check_playtomic(tenant_id: str, date) -> list:
    params = {
        "sport_id": "PADEL",
        "tenant_id": tenant_id,
        "start_min": f"{date}T00:00:00",
        "start_max": f"{date}T23:59:59",
        "duration": DURATION_MINUTES,
        "user_id": "me",
    }
    try:
        r = requests.get(PLAYTOMIC_API, params=params, headers=PLAYTOMIC_HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  Playtomic Fehler: {e}")
        return []

def filter_playtomic_slots(slots: list, date) -> list:
    matches = []
    for slot in slots:
        time_str = slot.get("start_time", "")[:5]
        if time_str in DESIRED_TIMES:
            matches.append({"date": str(date), "time": time_str})
    return matches

# ─────────────────────────────────────────
#  EVERSPORTS API
# ─────────────────────────────────────────

EVERSPORTS_API = "https://www.eversports.de/api/slot"
EVERSPORTS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.eversports.de/",
}

def check_eversports_all(facility_id: int, court_id: int) -> list:
    """Holt alle gebuchten Slots ab heute in einem Request."""
    today = datetime.now().date()
    params = {
        "facilityId": facility_id,
        "startDate": str(today),
        "courts[]": court_id,
    }
    try:
        r = requests.get(EVERSPORTS_API, params=params, headers=EVERSPORTS_HEADERS, timeout=10)
        r.raise_for_status()
        return r.json().get("slots", [])
    except Exception as e:
        print(f"  Eversports Fehler: {e}")
        return []

def filter_eversports_slots(all_slots: list, days: list) -> list:
    """API gibt gebuchte Slots – freie = Wunschzeiten die NICHT in der Liste stehen."""
    booked = {}
    for slot in all_slots:
        d = slot.get("date", "")
        raw = slot.get("start", "")
        if len(raw) == 4:
            time_str = f"{raw[:2]}:{raw[2:]}"
            booked.setdefault(d, set()).add(time_str)

    matches = []
    for day in days:
        date_str = str(day)
        booked_today = booked.get(date_str, set())
        for time_str in DESIRED_TIMES:
            # Prüfen ob der Slot UND der nächste 30-Min-Block frei sind (= 1 Stunde frei)
            h, m = int(time_str[:2]), int(time_str[3:])
            next_minutes = m + 30
            next_h = h + next_minutes // 60
            next_m = next_minutes % 60
            next_time = f"{next_h:02d}:{next_m:02d}"
            if time_str not in booked_today and next_time not in booked_today:
                matches.append({"date": date_str, "time": time_str})
    return matches

# ─────────────────────────────────────────
#  HILFSFUNKTIONEN
# ─────────────────────────────────────────

def get_weekdays_ahead(days: int):
    today = datetime.now().date()
    result = []
    for i in range(1, days + 1):
        day = today + timedelta(days=i)
        if day.weekday() < 5:
            result.append(day)
    return result

def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        print("Telegram-Nachricht gesendet!")
    except Exception as e:
        print(f"Fehler beim Senden: {e}")

def format_date_german(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d")
    weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    return f"{weekdays[d.weekday()]}, {d.strftime('%d.%m.')}"

# ─────────────────────────────────────────
#  STATS
# ─────────────────────────────────────────

def load_stats() -> dict:
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    return {
        "week_start": str(datetime.now().date()),
        "total_runs": 0, "successful_runs": 0,
        "slots_found": 0, "alerts_sent": 0,
    }

def save_stats(stats: dict):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

def send_weekly_summary(stats: dict):
    week_start = stats.get("week_start", "?")
    week_end = str(datetime.now().date())
    runs = stats.get("total_runs", 0)
    successful = stats.get("successful_runs", 0)
    slots = stats.get("slots_found", 0)
    alerts = stats.get("alerts_sent", 0)
    success_rate = round((successful / runs * 100) if runs > 0 else 0)
    message = (
        f"📊 <b>SlotBot Wochenbericht</b>\n"
        f"📅 {week_start} – {week_end}\n\n"
        f"🔍 Scraping-Runs: <b>{runs}x</b>\n"
        f"✅ Erfolgreich: <b>{successful}x</b> ({success_rate}%)\n"
        f"🎾 Freie Slots entdeckt: <b>{slots}x</b>\n"
        f"🔔 Benachrichtigungen gesendet: <b>{alerts}x</b>\n\n"
        f"Nächste Woche schrauben wir wieder! 💪"
    )
    send_telegram_message(message)

# ─────────────────────────────────────────
#  HAUPTPROGRAMM
# ─────────────────────────────────────────

def main():
    is_sunday_summary = os.environ.get("WEEKLY_SUMMARY") == "true"
    stats = load_stats()

    if is_sunday_summary:
        print("Sonntags-Zusammenfassung wird gesendet...")
        send_weekly_summary(stats)
        save_stats({
            "week_start": str(datetime.now().date()),
            "total_runs": 0, "successful_runs": 0,
            "slots_found": 0, "alerts_sent": 0,
        })
        return

    print(f"SlotBot startet – suche für {DAYS_AHEAD} Tage im Voraus...")
    stats["total_runs"] = stats.get("total_runs", 0) + 1
    all_found = []
    api_success = False
    days = get_weekdays_ahead(DAYS_AHEAD)

    for venue in VENUES:
        print(f"\n📍 Prüfe {venue['name']} ({venue['type']})...")

        if venue["type"] == "playtomic":
            for date in days:
                slots = check_playtomic(venue["tenant_id"], date)
                matches = filter_playtomic_slots(slots, date)
                if slots:
                    api_success = True
                for m in matches:
                    m["venue"] = venue
                all_found.extend(matches)
                print(f"  {date}: {len(matches)} Treffer")

        elif venue["type"] == "eversports":
            all_slots = check_eversports_all(venue["facility_id"], venue["court_id"])
            if all_slots:
                api_success = True
            matches = filter_eversports_slots(all_slots, days)
            for m in matches:
                m["venue"] = venue
            all_found.extend(matches)
            per_day = Counter(m["date"] for m in matches)
            for date in days:
                print(f"  {date}: {per_day.get(str(date), 0)} Treffer")

    if api_success:
        stats["successful_runs"] = stats.get("successful_runs", 0) + 1

    if not all_found:
        print("Keine freien Slots gefunden.")
    else:
        stats["slots_found"] = stats.get("slots_found", 0) + len(all_found)
        stats["alerts_sent"] = stats.get("alerts_sent", 0) + 1

        grouped = defaultdict(lambda: defaultdict(list))
        for m in all_found:
            grouped[m["venue"]["name"]][m["date"]].append(m["time"])

        lines = ["🎾 <b>SlotBot – Freie Padel-Courts!</b>\n"]
        for venue_name, dates in grouped.items():
            venue_obj = next(v for v in VENUES if v["name"] == venue_name)
            lines.append(f"📍 <b>{venue_name}</b>")
            sorted_dates = sorted(dates.keys())[:5]
            for date_str in sorted_dates:
                date_fmt = format_date_german(date_str)
                time_counts = Counter(dates[date_str])
                time_parts = []
                for t in sorted(time_counts.keys()):
                    count = time_counts[t]
                    time_parts.append(f"{t} ({count}x)" if count > 1 else t)
                lines.append(f"✅ {date_fmt} → {', '.join(time_parts)}")
            if len(dates) > 5:
                lines.append(f"... und {len(dates) - 5} weitere Tage verfügbar.")
            lines.append(f"🔗 <a href=\"{venue_obj['booking_url']}\">Jetzt buchen</a>\n")

        send_telegram_message("\n".join(lines))
        print(f"\n{len(all_found)} freie Slots gefunden und gesendet!")

    save_stats(stats)


if __name__ == "__main__":
    main()
