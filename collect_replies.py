import asyncio
import os
import csv
from telegram import Bot
# from dotenv import load_dotenv

# load_dotenv()  


BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

OFFSET_FILE = "last_offset.txt"
REPLIES_FILE = "replies.csv"

async def main():
    # Read last processed update so we don't save duplicates
    offset = 0
    if os.path.exists(OFFSET_FILE):
        with open(OFFSET_FILE, "r") as f:
            content = f.read().strip()
            if content:
                offset = int(content)

    async with Bot(token=BOT_TOKEN) as bot:
        updates = await bot.get_updates(offset=offset, timeout=10)

    if not updates:
        print("No new replies")
        return

    # Filter only messages from your chat
    new_replies = []
    for update in updates:
        if update.message and str(update.message.chat_id) == CHAT_ID:
            new_replies.append({
                "timestamp": update.message.date.isoformat(),
                "message": update.message.text,
            })

    # Append to CSV
    file_exists = os.path.exists(REPLIES_FILE)
    with open(REPLIES_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "message"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(new_replies)

    # Save offset so next run skips these updates
    with open(OFFSET_FILE, "w") as f:
        f.write(str(updates[-1].update_id + 1))

    print(f"Saved {len(new_replies)} new replies")

if __name__ == "__main__":
    asyncio.run(main())