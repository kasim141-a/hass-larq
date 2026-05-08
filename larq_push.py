#!/usr/bin/env python3
"""Fetch LARQ hydration data from Firebase RTDB and push to Home Assistant.

Configure via larq_config.json (see larq_config.example.json).
Run on a schedule (cron/launchd) every 5-30 minutes.
"""
import json
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_CONFIG_FILE = Path(__file__).parent / "larq_config.json"


def load_config() -> dict:
    if not _CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Config file not found: {_CONFIG_FILE}\n"
            "Copy larq_config.example.json to larq_config.json and fill in your values."
        )
    return json.loads(_CONFIG_FILE.read_text())


def refresh_firebase_token(api_key: str, refresh_token: str) -> str:
    body = json.dumps({"grantType": "refresh_token", "refreshToken": refresh_token})
    result = subprocess.run(
        ["curl", "-s", "-X", "POST",
         f"https://securetoken.googleapis.com/v1/token?key={api_key}",
         "-H", "Content-Type: application/json",
         "-d", body],
        capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    if "id_token" not in data:
        raise RuntimeError(f"Token refresh failed: {data}")
    return data["id_token"]


def fetch_rtdb(token: str, rtdb_url: str, path: str) -> dict:
    url = f"{rtdb_url}/{path}.json?auth={token}"
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())


def push_to_ha(ha_url: str, ha_token: str, entity_id: str, state: str, attributes: dict) -> None:
    data = json.dumps({"state": state, "attributes": attributes}).encode()
    req = urllib.request.Request(
        f"{ha_url}/api/states/{entity_id}",
        data=data,
        headers={"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req)


def main() -> None:
    cfg = load_config()

    token = refresh_firebase_token(cfg["firebase_api_key"], cfg["firebase_refresh_token"])

    today = datetime.now(timezone.utc).date().isoformat()
    raw = fetch_rtdb(token, cfg["firebase_rtdb_url"], f"liquidIntake/{cfg['firebase_uid']}")

    entries = list(raw.values()) if raw else []
    today_entries = [e for e in entries if e.get("time", "").startswith(today)]
    last = max(entries, key=lambda e: e.get("time", ""), default=None)

    today_ml = round(sum(e.get("volumeInLiter", 0) for e in today_entries) * 1000)
    last_time = last["time"] if last else None
    last_ml = round((last.get("volumeInLiter", 0) if last else 0) * 1000)
    goal_ml = cfg.get("daily_goal_ml", 2000)

    ha_url = cfg["ha_url"]
    ha_token = cfg["ha_token"]

    push_to_ha(ha_url, ha_token, "sensor.larq_water_today", str(today_ml), {
        "unit_of_measurement": "mL",
        "friendly_name": "LARQ Water Today",
        "icon": "mdi:cup-water",
        "state_class": "total_increasing",
        "drink_count_today": len(today_entries),
        "goal_ml": goal_ml,
        "percent_of_goal": round(today_ml / goal_ml * 100) if goal_ml else 0,
    })

    if last_time:
        push_to_ha(ha_url, ha_token, "sensor.larq_last_drink", last_time, {
            "friendly_name": "LARQ Last Drink",
            "icon": "mdi:water-clock",
            "device_class": "timestamp",
            "volume_ml": last_ml,
        })

    print(f"{datetime.now():%Y-%m-%d %H:%M} — {today_ml}mL today ({len(today_entries)} drinks), last: {last_time} ({last_ml}mL)")


if __name__ == "__main__":
    main()
