"""Create (or update) the reminder jobs on cron-job.org in one go.

Run it once on your own computer:
  set CRONJOB_API_KEY, TELEGRAM_TOKEN, CHAT_ID   (and optionally GH_TOKEN, GH_REPO)
  python setup_cronjobs.py

Running it again updates the same jobs, so you can change TIMES below and rerun.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

# Dhaka time, the same all year. Change and rerun if you want different times.
TIMES = {
    "Fajr": "04:35",
    "Dhuhr": "12:15",
    "Asr": "16:40",
    "Maghrib": "18:00",
    "Isha": "19:25",
}
REPORT_TIME = "23:30"  # only used if GH_TOKEN and GH_REPO are set
PREFIX = "Prayer bot - "

API = "https://api.cron-job.org"
KEY = os.environ.get("CRONJOB_API_KEY", "")
TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO", "")  # like "yourname/prayer-bot"


def call(method, path, body=None):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode()
        return json.loads(text) if text else {}


def schedule(hhmm):
    h, m = map(int, hhmm.split(":"))
    return {"timezone": "Asia/Dhaka", "expiresAt": 0, "hours": [h], "minutes": [m],
            "mdays": [-1], "months": [-1], "wdays": [-1]}


def reminder_job(prayer, hhmm):
    text = f"{prayer} reminder. Rate it when you're done (0 or 1-5)."
    url = (f"https://api.telegram.org/bot{TOKEN}/sendMessage?"
           + urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}))
    return {"title": PREFIX + prayer, "url": url, "enabled": True,
            "saveResponses": False, "requestMethod": 0, "schedule": schedule(hhmm)}


def report_job():
    """Starts the GitHub workflow at night, on time, instead of waiting for GitHub's lagging cron."""
    return {
        "title": PREFIX + "nightly report",
        "url": f"https://api.github.com/repos/{GH_REPO}/actions/workflows/bot.yml/dispatches",
        "enabled": True, "saveResponses": False, "requestMethod": 1,  # POST
        "extendedData": {
            "headers": {"Authorization": f"Bearer {GH_TOKEN}",
                        "Accept": "application/vnd.github+json",
                        "User-Agent": "prayer-bot"},
            "body": json.dumps({"ref": "main"}),
        },
        "schedule": schedule(REPORT_TIME),
    }


def main():
    missing = [n for n, v in [("CRONJOB_API_KEY", KEY), ("TELEGRAM_TOKEN", TOKEN), ("CHAT_ID", CHAT_ID)] if not v]
    if missing:
        sys.exit("Missing: " + ", ".join(missing))

    wanted = [reminder_job(p, t) for p, t in TIMES.items()]
    if GH_TOKEN and GH_REPO:
        wanted.append(report_job())

    existing = {j["title"]: j["jobId"] for j in call("GET", "/jobs").get("jobs", [])}
    for job in wanted:
        if job["title"] in existing:
            call("PATCH", f"/jobs/{existing[job['title']]}", {"job": job})
            print("updated ", job["title"], job["schedule"]["hours"], job["schedule"]["minutes"])
        else:
            res = call("PUT", "/jobs", {"job": job})
            print("created ", job["title"], "id", res.get("jobId"))
    print("Done. Check them at https://console.cron-job.org/jobs")


if __name__ == "__main__":
    main()
