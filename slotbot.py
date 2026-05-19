import requests
from datetime import datetime, timedelta
import os
import json

# ─────────────────────────────────────────
#  KONFIGURATION – hier alles anpassen
# ─────────────────────────────────────────

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# PadelCity München Tucherpark (Playtomic Tenant-ID)
VENUES = [
    {
        "name": "PadelCity München Tucherpark",
        "tenant_id": "ea2bccb9-ea75-486c-959f-921a65df4f32",
        "booking_url": "https://playtomic.io/padelcity-mnchen-tucherpark/ea2bccb9-ea75-486c-959f-921a65df4f32",
    }
]

# Gewünschte Startzeiten (Mo–Fr)
DESIRED_TIMES = ["16:30", "17:00", "17:30", "18:00", "18:30", "19:00"]

# Spieldauer in Minuten
DURATION_MINUTES = 60

# Wie viele Tage im Voraus suchen?
DAYS_AHEAD = 14

# Stats-Datei
STATS_FILE = "stats.json"

# ─────────────────────────────────────────
#  PLAYTOMIC API
# ─────────────────────────────────────────

API_BASE = "https://api.playtomic.io/v1/availability"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15",
    "Accept": "application/json",
    "X-Requested-With": "com.playtomic.app",
}


def get_weekdays_ahead(days: int):
    """Gibt alle Wochentage (Mo–Fr) der nächsten X Tage zurück."""
    today = datetime.now().date()
    result = []
    for i in range(1, days + 1):
        day = today + timedelta(days=i)
        if day.weekday() < 5:  # 0=Mo, 4=Fr
            result.append(day)
    return result


def check_availability(tenant_id: str, date) -> list:
    """Fragt Playtomic API für einen Tag ab und gibt freie Slots zurück."""
    start_min = f"{date}T00:00:00"
    start_max = f"{date}T23:59:59"

    params = {
        "sport_id": "PADEL",
        "tenant_id": tenant_id,
        "start_min": start_min,
        "start_max": start_max,
        "duration": DURATION_MINUTES,
        "user_id": "me",
    }

    try:
        response = requests.get(API_BASE, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Fehler bei API-Anfrage: {e}")
        return []


def filter_desired_slots(slots: list, date) -> list:
    """Filtert nur die gewünschten Zeiten heraus."""
    matches = []
    for slot in slots:
        start = slot.get("start_time", "")
        time_str = start[:5]
        if time_str in DESIRED_TIMES:
            matches.append({
                "date": str(date),
                "time": time_str,
                "slot": slot,
            })
    return matches


def send_telegram_message(text: str):
    """Sendet eine Nachricht an die Telegram-Gruppe."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        print("Telegram-Nachricht gesendet!")
    except Exception as e:
        print(f"Fehler beim Senden: {e}")


def format_date_german(date_str: str) -> str:
    """Formatiert Datum auf Deutsch: 2026-05-22 → Fr, 22.05."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    return f"{weekdays[d.weekday()]}, {d.strftime('%d.%m.')}"


# ─────────────────────────────────────────
#  STATS
# ─────────────────────────────────────────

def load_stats() -> dict:
    """Lädt die Stats-Datei oder erstellt eine neue."""
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    return {
        "week_start": str(datetime.now().date()),
        "total_runs": 0,
        "successful_runs": 0,
        "slots_found": 0,
        "alerts_sent": 0,
    }


def save_stats(stats: dict):
    """Speichert die Stats-Datei."""
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)


def send_weekly_summary(stats: dict):
    """Sendet die Wochenzusammenfassung an Telegram und resettet die Stats."""
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
        new_stats = {
            "week_start": str(datetime.now().date()),
            "total_runs": 0,
            "successful_runs": 0,
            "slots_found": 0,
            "alerts_sent": 0,
        }
        save_stats(new_stats)
        return

    print(f"SlotBot startet – suche für {DAYS_AHEAD} Tage im Voraus...")
    stats["total_runs"] = stats.get("total_runs", 0) + 1
    all_found = []
    api_success = False

    days = get_weekdays_ahead(DAYS_AHEAD)

    for venue in VENUES:
        print(f"\n📍 Prüfe {venue['name']}...")
        for date in days:
            slots = check_availability(venue["tenant_id"], date)
            if slots is not None:
                api_success = True
            matches = filter_desired_slots(slots, date)
            for m in matches:
                m["venue"] = venue
            all_found.extend(matches)
            print(f"  {date}: {len(matches)} Treffer")

    if api_success:
        stats["successful_runs"] = stats.get("successful_runs", 0) + 1

    if not all_found:
        print("Keine freien Slots gefunden.")
    else:
        stats["slots_found"] = stats.get("slots_found", 0) + len(all_found)
        stats["alerts_sent"] = stats.get("alerts_sent", 0) + 1

        lines = ["🎾 <b>SlotBot – Freie Padel-Courts!</b>\n"]
        for m in all_found:
            date_fmt = format_date_german(m["date"])
            venue_name = m["venue"]["name"]
            booking_url = m["venue"]["booking_url"]
            lines.append(
                f"✅ <b>{date_fmt} um {m['time']} Uhr</b>\n"
                f"📍 {venue_name}\n"
                f'🔗 <a href="{booking_url}">Jetzt buchen</a>\n'
            )

        message = "\n".join(lines)
        send_telegram_message(message)
        print(f"\n{len(all_found)} freie Slots gefunden und gesendet!")

    save_stats(stats)


if __name__ == "__main__":
    main()
