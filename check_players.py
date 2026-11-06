# Checks the Project Zomboid server's player count and posts
# "5 players online", "10 players online", etc. to Discord.
# - At most one message per hour
# - Never posts "0 players online"

import json
import os
import time

import a2s
import requests

IP = os.environ["SERVER_IP"]
PORT = int(os.environ["SERVER_PORT"])
WEBHOOK = os.environ["DISCORD_WEBHOOK"]
STEP = 5                  # announce every 5 players
COOLDOWN = 60 * 60        # seconds between messages (1 hour)
STATE_FILE = "state.json"

# What we remember between runs
try:
    with open(STATE_FILE) as f:
        state = json.load(f)
except Exception:
    state = {}
last = int(state.get("last_milestone", 0))
last_post = float(state.get("last_post_time", 0))

# Ask the game server how many players are on
try:
    players = a2s.info((IP, PORT), timeout=10).player_count
except Exception as e:
    print(f"Server unreachable, skipping this check: {e}")
    raise SystemExit(0)

milestone = (players // STEP) * STEP
now = time.time()
print(f"{players} players online (milestone {milestone}, last announced {last})")

new_last, new_post = last, last_post
if milestone > last and milestone > 0:
    if now - last_post >= COOLDOWN:
        r = requests.post(WEBHOOK, json={"content": f"{milestone} players online"}, timeout=10)
        r.raise_for_status()
        print(f"Posted: {milestone} players online")
        new_last, new_post = milestone, now
    else:
        mins = int((COOLDOWN - (now - last_post)) / 60) + 1
        print(f"Reached {milestone}, but waiting ~{mins} more min (1 message per hour)")
elif milestone < last and players <= last - 3:
    # Count dropped well below the last milestone -> allow it to announce again later.
    # (The 3-player buffer stops spam when someone keeps joining/leaving at 4-5.)
    new_last = milestone

if (new_last, new_post) != (last, last_post):
    with open(STATE_FILE, "w") as f:
        json.dump({"last_milestone": new_last, "last_post_time": new_post}, f)
