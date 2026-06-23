import asyncio
import os
import csv
from datetime import datetime, date, timezone, timedelta
from telegram import Bot
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

DHAKA_TZ = timezone(timedelta(hours=6))
REPLIES_FILE = "replies.csv"

# Each prayer "starts" at this time in Dhaka — any reply after this 
# and before the next prayer belongs to this prayer
PRAYER_SLOTS = [
    ("Fajr",     6,  0),
    ("Zuhr",    16, 30),
    ("Asr",     18,  0),
    ("Maghrib", 19, 30),
    ("Isha",    22, 30),
]

def get_prayer_for_time(dt):
    """Figure out which prayer a reply belongs to based on when it was sent."""
    minutes = dt.hour * 60 + dt.minute
    assigned = None
    for i, (name, hour, minute) in enumerate(PRAYER_SLOTS):
        slot_start = hour * 60 + minute
        slot_end = (PRAYER_SLOTS[i + 1][1] * 60 + PRAYER_SLOTS[i + 1][2]) if i + 1 < len(PRAYER_SLOTS) else 24 * 60 + 30
        if slot_start <= minutes < slot_end:
            assigned = name
            break
    return assigned

async def main():
    today = datetime.now(DHAKA_TZ).date()

    # Initialize all prayers as None (missing)
    ratings = {name: None for name, _, _ in PRAYER_SLOTS}

    if os.path.exists(REPLIES_FILE):
        with open(REPLIES_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = datetime.fromisoformat(row["timestamp"]).astimezone(DHAKA_TZ)
                if ts.date() == today:
                    try:
                        rating = int(row["message"].strip())
                        if 1 <= rating <= 5:
                            prayer = get_prayer_for_time(ts)
                            if prayer:
                                ratings[prayer] = rating
                    except ValueError:
                        pass

    prayers = [name for name, _, _ in PRAYER_SLOTS]
    values = [ratings[p] for p in prayers]

    # Separate into answered and unanswered for the chart
    answered_x = [p for p, v in zip(prayers, values) if v is not None]
    answered_y = [v for v in values if v is not None]

    if not answered_x:
        async with Bot(token=BOT_TOKEN) as bot:
            await bot.send_message(chat_id=CHAT_ID, text="No ratings found for today!")
        return

    # Figure out which prayers were missed
    missed = [p for p, v in zip(prayers, values) if v is None]
    missed_text = f"Missing replies: {', '.join(missed)}" if missed else " All prayers answered!"

    # Draw chart
    plt.figure(figsize=(8, 5))
    plt.plot(answered_x, answered_y, marker='o', linewidth=2, markersize=8, color='#2196F3')

    # Mark missing prayers with a red X on the x axis
    for prayer in missed:
        plt.axvline(x=prayer, color='red', linestyle='--', alpha=0.4)

    plt.title(f"Prayer Ratings — {today.strftime('%B %d, %Y')}", fontsize=14, fontweight='bold')
    plt.xlabel("Prayer", fontsize=12)
    plt.ylabel("Rating (1-5)", fontsize=12)
    plt.xticks(prayers)
    plt.ylim(0.5, 5.5)
    plt.yticks([1, 2, 3, 4, 5])
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig("chart.png", dpi=150)
    plt.close()

    async with Bot(token=BOT_TOKEN) as bot:
        with open("chart.png", "rb") as photo:
            await bot.send_photo(
                chat_id=CHAT_ID,
                photo=photo,
                caption=f"Your prayer ratings for today!\n{missed_text}"
            )

if __name__ == "__main__":
    asyncio.run(main())