# 🤖 SlotBot

Automatischer Padel-Court-Scraper für München – läuft kostenlos in der Cloud via GitHub Actions und schickt Benachrichtigungen bei Änderungen in eine Telegram-Gruppe.

## Was er macht
- Prüft alle 15 Minuten freie Padel-Courts bei **PadelCity München** (Playtomic) und **Sport Insel Taufkirchen** (Eversports)
- Schickt nur eine Nachricht wenn sich etwas geändert hat (neu frei oder weggebucht)
- Wöchentlicher Bericht jeden Sonntag

## Setup
1. Telegram Bot erstellen via @BotFather → Token speichern
2. Bot in Padel-Gruppe einladen → Chat-ID herausfinden
3. GitHub Secrets hinterlegen: `TELEGRAM_TOKEN` und `TELEGRAM_CHAT_ID`
4. Fertig – SlotBot läuft automatisch

## Konfiguration
Alle Einstellungen in `slotbot.py`:
- `DESIRED_TIMES` – gewünschte Startzeiten
- `DAYS_AHEAD` – wie viele Tage im Voraus suchen
- `VENUES` – Anbieter hinzufügen oder entfernen

---
*Gebaut mit ❤️ für die Padel-Community München*
