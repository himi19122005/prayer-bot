import asyncio
import os
from telegram import Bot
# from dotenv import load_dotenv

# load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
MESSAGE_SLOT = os.environ.get("MESSAGE_SLOT", "fajr")

MESSAGES = {
    "fajr":    "What is the quality of fazr?",
    "zuhr":    "What is the quality of zuhr?",
    "asr":     "What is the quality of asr?",
    "maghrib": "What is the quality of magrib?",
    "isha":    "What is the quality of isha?",
}

async def main():
    async with Bot(token=BOT_TOKEN) as bot:
        await bot.send_message(chat_id=CHAT_ID, text=MESSAGES[MESSAGE_SLOT])

if __name__ == "__main__":
    asyncio.run(main())