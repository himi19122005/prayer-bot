import asyncio
import os
import csv
from datetime import datetime, timezone, timedelta
from telegram import Bot
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

PRAYERS = ["Fajr", "Zuhr", "Asr", "Maghrib", "Isha"]
DHAKA_TZ = timezone(timedelta(hours=6))
REPLIES_FILE = "replies.csv"

async def main():
    now = datetime.now(DHAKA_TZ)
    # if running after midnight, look at yesterday's data
    if now.hour < 6:
        today = (now - timedelta(days=1)).date()
    else:
        today = now.date()

    ratings = []
    if os.path.exists(REPLIES_FILE):
        with open(REPLIES_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = datetime.fromisoformat(row["timestamp"]).astimezone(DHAKA_TZ)
                if ts.date() == today:
                    try:
                        rating = float(row["message"].strip())
                        if 1 <= rating <= 5:
                            ratings.append(rating)
                    except ValueError:
                        pass

    if not ratings:
        async with Bot(token=BOT_TOKEN) as bot:
            await bot.send_message(chat_id=CHAT_ID, text="No ratings found for today!")
        return

    ratings = ratings[:5]
    prayers = PRAYERS[:len(ratings)]

    plt.figure(figsize=(8, 5))
    plt.plot(prayers, ratings, marker='o', linewidth=2, markersize=8, color='#2196F3')
    plt.title(f"Prayer Ratings — {today.strftime('%B %d, %Y')}", fontsize=14, fontweight='bold')
    plt.xlabel("Prayer", fontsize=12)
    plt.ylabel("Rating (1-5)", fontsize=12)
    plt.ylim(0.5, 5.5)
    plt.yticks([1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5]) 
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig("chart.png", dpi=150)
    plt.close()

    async with Bot(token=BOT_TOKEN) as bot:
        with open("chart.png", "rb") as photo:
            await bot.send_photo(
                chat_id=CHAT_ID,
                photo=photo,
                caption=f" Your prayer ratings for today!"
            )

if __name__ == "__main__":
    asyncio.run(main())