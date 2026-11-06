# Posts the server restart messages (Eastern time):
#   5:55am/pm  "The server restarts in 5 minutes"
#   6:00am/pm  "It's 6 o'clock, the server is rebooting. Your progress is saved."
# GitHub starts this a while early; it waits for the exact minute before posting.

import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

WEBHOOK = os.environ["DISCORD_WEBHOOK"]
TZ = ZoneInfo("America/New_York")

WARNING = "The server restarts in 5 minutes"
REBOOT = "It's 6 o'clock, the server is rebooting. Your progress is saved."


def post(text):
    r = requests.post(WEBHOOK, json={"content": text}, timeout=10)
    r.raise_for_status()
    print(f"Posted: {text}")


def wait_until(t):
    seconds = (t - datetime.now(TZ)).total_seconds()
    if seconds > 0:
        print(f"Waiting until {t:%I:%M %p} Eastern...")
        time.sleep(seconds)


if os.environ.get("TEST_MODE") == "true":
    # Test run (manual "Run workflow"): post both messages right away
    post("TEST MESSAGE: " + WARNING)
    post("TEST MESSAGE: " + REBOOT)
    raise SystemExit(0)

now = datetime.now(TZ)
if now.hour not in (5, 17):
    print(f"It's {now:%I:%M %p} Eastern, not the hour before a restart. Nothing to do.")
    raise SystemExit(0)

warn_at = now.replace(minute=55, second=0, microsecond=0)
reboot_at = now.replace(hour=now.hour + 1, minute=0, second=0, microsecond=0)

if now < warn_at.replace(minute=58):   # too late for a 5-minute warning after 5:58
    wait_until(warn_at)
    post(WARNING)
else:
    print("Started too late for the 5-minute warning; skipping it")

wait_until(reboot_at)
if datetime.now(TZ) < reboot_at.replace(minute=10):
    post(REBOOT)
