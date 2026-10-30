"""Prayer quality bot.

Reminders are sent by cron-job.org (see setup_cronjobs.py). This script runs on
GitHub Actions: it saves your Telegram replies, turns them into ratings and sends
the daily / weekly / monthly reports.

Usage:
  python bot.py                  normal run (collect replies, report if it is night)
  python bot.py --force daily    also send a report now (daily|weekly|monthly|all)
  python bot.py --selftest       test the parser and draw sample charts, no Telegram
"""
import csv
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import uuid
from datetime import date, datetime, timedelta, timezone

PRAYERS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
DHAKA = timezone(timedelta(hours=6))
HERE = os.path.dirname(os.path.abspath(__file__))
MESSAGES_CSV = os.path.join(HERE, "messages.csv")
RATINGS_CSV = os.path.join(HERE, "ratings.csv")
REPORTED_JSON = os.path.join(HERE, "reported.json")

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")


# ---------- rating rules ----------

def is_red(r):
    """A rating counts as 'a 1' when 1 <= r < 2. Zero is never red."""
    return r is not None and 1 <= r < 2


def counts(r):
    """Zero means 'does not count': it is left out of averages."""
    return r is not None and r != 0


def parse_value(s):
    try:
        v = float(s)
    except ValueError:
        return None
    if v == 0 or 1 <= v <= 5:
        return v
    return None


def fmt(v):
    return f"{v:g}"


def parse(messages):
    """Turn the message log into ratings.

    messages: list of (update_id, unix_ts, text) in the order they were sent.
    Returns (ratings, notes) where ratings is {date: [r0..r4 or None]} and
    notes is {update_id: [text lines to tell the user]}.
    """
    ratings = {}
    history = []  # (date, slot) of every accepted rating, for undo
    notes = {}

    def slots(d):
        return ratings.setdefault(d, [None] * 5)

    for uid, ts, text in messages:
        day = datetime.fromtimestamp(ts, DHAKA).date()
        out = notes.setdefault(uid, [])
        clean = text.strip().lower()
        if not clean or clean.startswith("/"):
            continue
        if clean == "undo":
            if not history:
                out.append("Nothing to undo.")
                continue
            d, i = history.pop()
            old = ratings[d][i]
            ratings[d][i] = None
            out.append(f"Undone: {PRAYERS[i]} {d:%d %b} ({fmt(old)}) removed.")
            continue

        # "y 3" -> "y3", then split on spaces / commas so "3 4 5" also works
        clean = re.sub(r"\by\s+", "y", clean)
        for tok in re.split(r"[\s,]+", clean):
            if not tok:
                continue
            target, label, raw = day, "today", tok
            if tok.startswith("y"):
                target, label, raw = day - timedelta(days=1), "yesterday", tok[1:]
            v = parse_value(raw)
            if v is None:
                out.append(f"Not a rating: {tok} (use 0 or 1-5). Ignored.")
                continue
            s = slots(target)
            if None not in s:
                if label == "today":
                    out.append(f"Today already has 5 ratings, {tok} ignored. Send undo first to change one.")
                else:
                    out.append(f"Yesterday is already complete, {tok} ignored.")
                continue
            i = s.index(None)
            s[i] = v
            history.append((target, i))
            out.append(f"{PRAYERS[i]} {target:%d %b}: {fmt(v)}")
    return ratings, notes


# ---------- storage ----------

def load_messages():
    if not os.path.exists(MESSAGES_CSV):
        return []
    with open(MESSAGES_CSV, newline="", encoding="utf-8") as f:
        return [(int(r["update_id"]), int(r["ts"]), r["text"]) for r in csv.DictReader(f)]


def save_messages(msgs):
    with open(MESSAGES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["update_id", "ts", "text"])
        w.writerows(msgs)


def save_ratings(ratings):
    with open(RATINGS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "prayer", "rating"])
        for d in sorted(ratings):
            for p, r in zip(PRAYERS, ratings[d]):
                w.writerow([d.isoformat(), p, "" if r is None else fmt(r)])


def load_reported():
    if not os.path.exists(REPORTED_JSON):
        return {}
    with open(REPORTED_JSON, encoding="utf-8") as f:
        return json.load(f)


def save_reported(rep):
    with open(REPORTED_JSON, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2)


# ---------- telegram ----------

def api(method, data=None, files=None):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    if files:
        boundary = uuid.uuid4().hex
        body = b""
        for k, v in (data or {}).items():
            body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
        for k, path in files.items():
            with open(path, "rb") as f:
                content = f.read()
            body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; "
                     f"filename=\"{os.path.basename(path)}\"\r\nContent-Type: image/png\r\n\r\n").encode()
            body += content + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    else:
        req = urllib.request.Request(url, urllib.parse.urlencode(data or {}).encode())
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def send_photo(path, caption):
    api("sendPhoto", {"chat_id": CHAT_ID, "caption": caption}, {"photo": path})


def fetch_new(known):
    """Get new messages from your chat. Telegram keeps them for 24 hours."""
    offset = max((u for u, _, _ in known), default=0) + 1
    res = api("getUpdates", {"offset": offset, "timeout": 0})
    new = []
    for u in res.get("result", []):
        m = u.get("message")
        if m and str(m["chat"]["id"]) == str(CHAT_ID) and "text" in m:
            new.append((u["update_id"], m["date"], m["text"]))
        offset = u["update_id"] + 1
    # confirm the updates so Telegram does not send them again
    api("getUpdates", {"offset": offset, "timeout": 0})
    return new


# ---------- reports ----------

def day_ratings(ratings, d):
    return ratings.get(d, [None] * 5)


def avg(values):
    vals = [v for v in values if counts(v)]
    return sum(vals) / len(vals) if vals else None


def fmt_avg(a):
    return "-" if a is None else f"{a:.2f}"


def week_days(friday):
    return [friday - timedelta(days=6 - i) for i in range(7)]  # Saturday..Friday


def month_days(d):
    first = d.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    return [first + timedelta(days=i) for i in range((nxt - first).days)]


def daily_report(ratings, d, out_dir):
    import charts
    r = day_ratings(ratings, d)
    path = os.path.join(out_dir, f"daily_{d}.png")
    charts.daily_chart(d, r, path)
    lines = [f"Daily report, {d:%a %d %b %Y}", f"Average: {fmt_avg(avg(r))}"]
    missing = [p for p, v in zip(PRAYERS, r) if v is None]
    if missing:
        lines.append("Not rated: " + ", ".join(missing))
    return [(path, "\n".join(lines))]


def weekly_report(ratings, friday, out_dir):
    import charts
    days = week_days(friday)
    grid = [day_ratings(ratings, d) for d in days]
    p1 = os.path.join(out_dir, f"weekly_lines_{friday}.png")
    p2 = os.path.join(out_dir, f"weekly_days_{friday}.png")
    charts.weekly_lines(days, grid, p1)
    charts.weekly_days(days, grid, p2)
    red_days = sum(any(is_red(v) for v in r) for r in grid)
    per = [avg([r[i] for r in grid]) for i in range(5)]
    cap1 = (f"Weekly report, {days[0]:%d %b} - {days[-1]:%d %b}\n"
            + "\n".join(f"{p}: {fmt_avg(a)}" for p, a in zip(PRAYERS, per))
            + f"\nOverall: {fmt_avg(avg([v for r in grid for v in r]))}")
    cap2 = f"{red_days} of 7 days had a 1 (a rating from 1 to below 2) in at least one prayer."
    return [(p1, cap1), (p2, cap2)]


def monthly_report(ratings, d, out_dir):
    import charts
    days = month_days(d)
    grid = [day_ratings(ratings, x) for x in days]
    path = os.path.join(out_dir, f"monthly_{d:%Y-%m}.png")
    charts.monthly_heatmap(days, grid, path)
    per = [avg([r[i] for r in grid]) for i in range(5)]
    red_days = sum(any(is_red(v) for v in r) for r in grid)
    unrated = sum(v is None for r in grid for v in r)
    cap = (f"Monthly report, {d:%B %Y}\n"
           + "\n".join(f"{p}: {fmt_avg(a)}" for p, a in zip(PRAYERS, per))
           + f"\nOverall: {fmt_avg(avg([v for r in grid for v in r]))}"
           + f"\nDays with a 1: {red_days}\nPrayers not rated: {unrated}")
    return [(path, cap)]


def is_last_day_of_month(d):
    return (d + timedelta(days=1)).day == 1


# ---------- main ----------

def run(force):
    if not TOKEN or not CHAT_ID:
        sys.exit("Set TELEGRAM_TOKEN and CHAT_ID.")
    msgs = load_messages()
    msgs += fetch_new(msgs)
    save_messages(msgs)
    ratings, _ = parse(msgs)
    save_ratings(ratings)

    now = datetime.now(DHAKA)
    report_day = now.date() if now.hour >= 6 else now.date() - timedelta(days=1)
    rep = load_reported()
    out_dir = os.path.join(HERE, "out")
    os.makedirs(out_dir, exist_ok=True)

    # The 13:00 run only saves replies. GitHub can start it hours late, so it must never report.
    collect_only = os.environ.get("MODE") == "collect"
    night = not collect_only and (now.hour >= 23 or now.hour < 6)
    jobs = []
    if (night and rep.get("daily") != str(report_day)) or force in ("daily", "all"):
        jobs.append(("daily", daily_report))
    if (night and report_day.weekday() == 4 and rep.get("weekly") != str(report_day)) or force in ("weekly", "all"):
        jobs.append(("weekly", weekly_report))
    if (night and is_last_day_of_month(report_day) and rep.get("monthly") != str(report_day)) or force in ("monthly", "all"):
        jobs.append(("monthly", monthly_report))

    for name, fn in jobs:
        d = report_day
        if name == "weekly" and d.weekday() != 4:  # forced: use the last Friday
            d -= timedelta(days=(d.weekday() - 4) % 7)
        for path, caption in fn(ratings, d, out_dir):
            send_photo(path, caption)
        if night:
            rep[name] = str(report_day)
    save_reported(rep)


def selftest():
    def ts(y, m, d, h, mi=0):
        return int(datetime(y, m, d, h, mi, tzinfo=DHAKA).timestamp())

    msgs = [
        # 1 Oct: all five at night, in order
        (1, ts(2026, 10, 1, 22), "3"), (2, ts(2026, 10, 1, 22, 1), "4.5"),
        (3, ts(2026, 10, 1, 22, 2), "2 5, 1.5"),
        # 2 Oct: Fajr rated before any reminder, Maghrib and Isha forgotten
        (4, ts(2026, 10, 2, 4, 10), "4"), (5, ts(2026, 10, 2, 13), "1"), (6, ts(2026, 10, 2, 17), "3"),
        # 3 Oct morning: yesterday's Maghrib and Isha, then today's Fajr
        (7, ts(2026, 10, 3, 6), "y2"), (8, ts(2026, 10, 3, 6, 1), "Y 3"), (9, ts(2026, 10, 3, 6, 2), "5"),
        (10, ts(2026, 10, 3, 6, 3), "y4"),          # yesterday already complete
        (11, ts(2026, 10, 3, 12), "7"),             # out of range
        (12, ts(2026, 10, 3, 12, 1), "0.5"),        # out of range
        (13, ts(2026, 10, 3, 12, 2), "0"),          # zero is allowed
        (14, ts(2026, 10, 3, 12, 3), "undo"),       # removes the 0
        (15, ts(2026, 10, 3, 12, 4), "4 4 4 4"),    # Dhuhr..Isha
        (16, ts(2026, 10, 3, 22), "4"),             # today full
        (17, ts(2026, 10, 3, 22, 1), "/start"),     # ignored silently
    ]
    ratings, notes = parse(msgs)
    d = date(2026, 10, 1)
    expect = {
        d: [3, 4.5, 2, 5, 1.5],
        d + timedelta(1): [4, 1, 3, 2, 3],
        d + timedelta(2): [5, 4, 4, 4, 4],
    }
    for k, v in expect.items():
        assert ratings[k] == v, (k, ratings[k], v)
    assert any("already complete" in n for n in notes[10])
    assert any("Not a rating: 7" in n for n in notes[11])
    assert any("Not a rating: 0.5" in n for n in notes[12])
    assert any("Undone" in n for n in notes[14])
    assert any("already has 5" in n for n in notes[16])
    assert notes[17] == []
    assert is_red(1) and is_red(1.9) and not is_red(2) and not is_red(0)
    print("parser: all checks passed")
    for uid in sorted(notes):
        for n in notes[uid]:
            print(f"  [{uid}] {n}")

    # sample charts from fake data for a whole month
    import random
    random.seed(4)
    fake = {}
    for day in month_days(date(2026, 10, 1)):
        row = [random.choice([2.5, 3, 3.5, 3.5, 4, 4, 4.5, 4.5, 5]) for _ in PRAYERS]
        if random.random() < 0.25:
            row[random.randrange(5)] = random.choice([1, 1.5])
        if random.random() < 0.3:
            row[4] = None   # forgot Isha
        if random.random() < 0.08:
            row[0] = 0
        fake[day] = row
    out_dir = os.path.join(HERE, "out")
    os.makedirs(out_dir, exist_ok=True)
    for path, cap in (daily_report(fake, date(2026, 10, 2), out_dir)
                      + weekly_report(fake, date(2026, 10, 16), out_dir)
                      + monthly_report(fake, date(2026, 10, 31), out_dir)):
        print(f"\n{path}\n{cap}")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        force = os.environ.get("FORCE", "")
        if "--force" in sys.argv:
            force = sys.argv[sys.argv.index("--force") + 1]
        run(force.strip().lower())
