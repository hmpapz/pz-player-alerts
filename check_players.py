# Project Zomboid player-count alerts for Discord (Eastern time).
#
# - Every rise of 5 (5, 10, 15...) posts right away with the real count: "12 players online"
# - Top of each hour: posts the current count (if 5+), and resets so rises can be announced again.
#   If a higher-or-equal count was posted in the last 20 minutes, it waits until those 20 minutes pass.
# - At 6:01am/pm (after the server restart) it resets to 0, so players rejoining get announced.
# - Never posts "0 players online"; skips the hourly update at 6am/pm (restart messages cover it).

import json
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import a2s
import requests

IP = os.environ["SERVER_IP"]
PORT = int(os.environ["SERVER_PORT"])
WEBHOOK = os.environ["DISCORD_WEBHOOK"]

STEP = 5                  # announce every 5 players
HOLD_MINUTES = 20         # hourly update waits this long after a recent higher/equal post
RESTART_HOURS = (6, 18)   # 6am and 6pm
RESET_MINUTE = 1          # reset to 0 at 6:01
TZ = ZoneInfo("America/New_York")
STATE_FILE = "state.json"
TEST_MODE = os.environ.get("TEST_MODE") == "true"  # manual "Run workflow" = test

# ---- what we remember between runs ----
try:
    with open(STATE_FILE) as f:
        state = json.load(f)
except Exception:
    state = {}
old_state = dict(state)
baseline = int(state.get("baseline", state.get("last_milestone", 0)))
last_post_time = float(state.get("last_post_time", 0))
last_post_count = int(state.get("last_post_count", baseline))
hour_reset = state.get("hour_reset", "")
hourly_done = state.get("hourly_done", "")
restart_reset = state.get("restart_reset", "")

now_ts = time.time()
now = datetime.fromtimestamp(now_ts, TZ)
hour_key = now.strftime("%Y-%m-%d %H")


def save():
    new = {
        "baseline": baseline,
        "last_post_time": last_post_time,
        "last_post_count": last_post_count,
        "hour_reset": hour_reset,
        "hourly_done": hourly_done,
        "restart_reset": restart_reset,
    }
    if new != old_state:
        with open(STATE_FILE, "w") as f:
            json.dump(new, f, indent=1)


def post(count):
    global last_post_time, last_post_count
    r = requests.post(WEBHOOK, json={"content": f"{count} players online"}, timeout=10)
    r.raise_for_status()
    last_post_time, last_post_count = now_ts, count
    print(f"Posted: {count} players online")


# ---- after a restart (6:01am/pm): start counting from 0 ----
latest_reset = None
for days_back in (0, 1):
    day = now - timedelta(days=days_back)
    for h in RESTART_HOURS:
        point = day.replace(hour=h, minute=RESET_MINUTE, second=0, microsecond=0)
        if point <= now and (latest_reset is None or point > latest_reset):
            latest_reset = point
reset_key = latest_reset.strftime("%Y-%m-%d %H:%M")
if reset_key != restart_reset:
    if restart_reset:  # (not on the very first run)
        print(f"Restart reset ({reset_key}): counting from 0")
        baseline = 0
    restart_reset = reset_key

# ---- ask the game server how many players are on ----
try:
    players = a2s.info((IP, PORT), timeout=10).player_count
except Exception as e:
    print(f"Server unreachable, skipping this check: {e}")
    save()
    raise SystemExit(0)

if TEST_MODE:
    # Test run: post the current count right away, and don't change what the bot remembers
    r = requests.post(WEBHOOK, json={"content": f"TEST MESSAGE: {players} players online"}, timeout=10)
    r.raise_for_status()
    print(f"Posted: TEST MESSAGE: {players} players online")
    raise SystemExit(0)

milestone = (players // STEP) * STEP
print(f"{now:%I:%M %p} Eastern: {players} players online (milestone {milestone}, baseline {baseline})")

# ---- top of the hour: reset so rises can be announced again ----
if hour_reset != hour_key:
    baseline = min(baseline, milestone)
    hour_reset = hour_key

# ---- a rise of 5: post right away ----
if milestone > baseline and milestone >= STEP:
    post(players)
    baseline = milestone
    hourly_done = hour_key  # counts as this hour's update

# ---- hourly update ----
elif hourly_done != hour_key:
    minutes_since = (now_ts - last_post_time) / 60
    if now.hour in RESTART_HOURS:
        print("Restart hour: skipping the hourly update")
        hourly_done = hour_key
    elif players < STEP:
        print("Fewer than 5 players: no hourly update")
        hourly_done = hour_key
    elif minutes_since < HOLD_MINUTES and last_post_count >= players:
        print(f"Holding hourly update: {last_post_count} was posted {int(minutes_since)} min ago")
    else:
        post(players)
        hourly_done = hour_key

save()
