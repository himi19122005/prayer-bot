# Prayer quality bot

Reminds you to rate each prayer (0 or 1-5, decimals allowed) and sends daily,
weekly (Friday) and monthly chart reports on Telegram. Times are for Dhaka.

- **Reminders** come from cron-job.org, on time to the minute.
- **Saving replies and reports** run on GitHub Actions (free for public repos).

## How to rate

Just send numbers. They fill today's prayers in order: Fajr, Dhuhr, Asr, Maghrib, Isha.

| You send | What happens |
|---|---|
| `3` | next empty prayer of today = 3 |
| `3 4.5 2` | three prayers at once |
| `y3` | next empty prayer of **yesterday** = 3 (only works the next day) |
| `y2` then `y3` | yesterday's Maghrib = 2, Isha = 3 (if those two were missing) |
| `0` | allowed, never red, not counted in averages |
| `undo` | removes the last rating you sent |
| a 6th number in a day | ignored, with a warning. Use `undo` first. |
| `y3` when yesterday is full | ignored, with a warning |
| `7`, `0.5`, words | ignored, with a warning |

A rating from 1 up to (not including) 2 counts as "a 1" and is shown in red.
Confirmations and warnings come at 13:00 and 23:30, not instantly.

## Reminder times (Dhaka, all year)

Fajr 04:35, Dhuhr 12:15, Asr 16:40, Maghrib 18:00, Isha 19:25.
These were picked from the full year of Dhaka prayer times so each reminder lands
within about an hour of the prayer starting. Change them in `setup_cronjobs.py`.

## Setup

### 1. Telegram
1. Make a bot with @BotFather and copy its **token**.
2. Send your bot any message, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser.
   Your **chat id** is the number at `"chat":{"id": ...`.

### 2. GitHub
1. Put all these files in a **public** repo (branch `main`).
2. Repo > Settings > Secrets and variables > Actions > New repository secret:
   `BOT_TOKEN` and `CHAT_ID`.
3. Actions tab > "prayer bot" > Run workflow (leave the box empty) to check it works.

### 3. cron-job.org (no forms to fill)
1. Sign up at cron-job.org. Settings > API > create an API key.
2. Optional but recommended, so the nightly report is on time: GitHub > Settings >
   Developer settings > Fine-grained tokens > new token for this repo only,
   permission **Actions: Read and write**.
3. On your computer, in this folder (PowerShell):

```powershell
$env:CRONJOB_API_KEY="..."; $env:TELEGRAM_TOKEN="..."; $env:CHAT_ID="..."
$env:GH_TOKEN="..."; $env:GH_REPO="yourname/your-repo"   # optional, from step 2
python setup_cronjobs.py
```

This creates the 5 reminders (plus the 23:30 report trigger if you set GH_TOKEN).
Run it again any time you change the times; it updates the same jobs.

## Testing

```powershell
python bot.py --selftest
```

Checks the rating rules and draws sample charts into `out/`.
On GitHub you can force a report: Run workflow, type `daily`, `weekly`, `monthly` or `all`.

## Good to know
- The repo is public, so `ratings.csv` and `messages.csv` can be seen by anyone.
  Your tokens stay secret.
- The cron-job.org reminder URLs contain your bot token. If it ever leaks,
  make a new one with @BotFather, update the GitHub secret, and rerun `setup_cronjobs.py`.
- The weekly report goes out Friday night. A `y` rating sent on Saturday for
  Friday's Isha still lands in the monthly report.
