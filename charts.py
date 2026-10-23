"""Chart drawing for the prayer bot. Each function writes one PNG."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch

PRAYERS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]

BG = "#FAF8F5"
INK = "#2B2B33"
MUTED = "#9A97A3"
GRID = "#E9E5DF"
RED = "#E5484D"
EMPTY = "#D9D5CF"
SCALE = ["#E5484D", "#F2994A", "#F2C94C", "#8BC34A", "#2E9E6B"]  # 1 .. 5
LINE_COLORS = ["#5B6CF0", "#F2994A", "#2E9E6B", "#C2569B", "#2BA6C9"]
CMAP = LinearSegmentedColormap.from_list("rating", SCALE)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": MUTED,
})


def color_for(r):
    if r is None or r == 0:
        return EMPTY
    if r < 2:
        return RED
    return CMAP((min(r, 5) - 1) / 4)


def _fig(w, h):
    fig, ax = plt.subplots(figsize=(w, h), dpi=150)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    for s in ax.spines.values():
        s.set_visible(False)
    return fig, ax


def _title(fig, title, subtitle):
    # positions in inches from the top, so short and tall charts look the same
    h = fig.get_figheight()
    fig.text(0.06, 1 - 0.28 / h, title, fontsize=17, fontweight="bold", va="top")
    fig.text(0.06, 1 - 0.64 / h, subtitle, fontsize=11, color=MUTED, va="top")


def _save(fig, path):
    fig.savefig(path, facecolor=BG)
    plt.close(fig)


def daily_chart(day, ratings, path):
    fig, ax = _fig(8, 5)
    fig.subplots_adjust(left=0.08, right=0.97, top=0.78, bottom=0.12)
    vals = [r for r in ratings if r is not None and r != 0]
    avg = sum(vals) / len(vals) if vals else None
    _title(fig, f"{day:%A, %d %B}",
           "Average " + (f"{avg:.2f} / 5" if avg is not None else "-")
           + f"   |   {sum(r is not None for r in ratings)} of 5 rated")

    width = 0.62
    for i, r in enumerate(ratings):
        x = i - width / 2
        if r is None:
            ax.add_patch(FancyBboxPatch((x, 0), width, 5, boxstyle="round,pad=0,rounding_size=0.12",
                                        fill=False, ec=EMPTY, lw=1.6, ls=(0, (4, 3))))
            ax.text(i, 2.5, "not\nrated", ha="center", va="center", color=MUTED, fontsize=10)
            continue
        # faint track, then the bar
        ax.add_patch(FancyBboxPatch((x, 0), width, 5, boxstyle="round,pad=0,rounding_size=0.12",
                                    fc=GRID, ec="none"))
        if r > 0:
            ax.add_patch(FancyBboxPatch((x, 0), width, r, boxstyle="round,pad=0,rounding_size=0.12",
                                        fc=color_for(r), ec="none"))
        ax.text(i, max(r, 0) + 0.15, f"{r:g}", ha="center", va="bottom",
                fontsize=14, fontweight="bold", color=INK if r else MUTED)

    ax.set_xlim(-0.6, 4.6)
    ax.set_ylim(0, 5.7)
    ax.set_xticks(range(5), PRAYERS, fontsize=12)
    ax.set_yticks([])
    ax.tick_params(length=0)
    _save(fig, path)


def weekly_lines(days, grid, path):
    fig, ax = _fig(9, 5.2)
    fig.subplots_adjust(left=0.07, right=0.80, top=0.78, bottom=0.12)
    _title(fig, "This week, prayer by prayer", f"{days[0]:%d %b} - {days[-1]:%d %b}")

    ax.axhspan(1, 2, color=RED, alpha=0.07, lw=0)
    for i, (p, c) in enumerate(zip(PRAYERS, LINE_COLORS)):
        ys = [r[i] if r[i] not in (None, 0) else float("nan") for r in grid]
        ax.plot(range(7), ys, color=c, lw=2.4, marker="o", ms=7,
                mec=BG, mew=1.5, label=p, solid_capstyle="round")

    ax.set_ylim(0.6, 5.4)
    ax.set_xlim(-0.3, 6.3)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_xticks(range(7), [f"{d:%a}\n{d:%d}" for d in days])
    ax.grid(axis="y", color=GRID, lw=1)
    ax.tick_params(length=0)
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False, fontsize=11)
    _save(fig, path)


def weekly_days(days, grid, path):
    fig, ax = _fig(9, 2.6)
    fig.subplots_adjust(left=0.03, right=0.97, top=0.62, bottom=0.03)
    red_days = [any(r is not None and 1 <= r < 2 for r in row) for row in grid]
    _title(fig, f"{sum(red_days)} of 7 days had a 1",
           "Red = at least one prayer rated from 1 to below 2")

    for i, (d, row, red) in enumerate(zip(days, grid, red_days)):
        rated = [r for r in row if r is not None]
        fc = RED if red else ("#2E9E6B" if rated else EMPTY)
        ax.add_patch(FancyBboxPatch((i + 0.06, 0.06), 0.88, 0.88,
                                    boxstyle="round,pad=0,rounding_size=0.1", fc=fc, ec="none"))
        txt = "white" if rated or red else INK
        ax.text(i + 0.5, 0.80, f"{d:%a}", ha="center", va="center", color=txt, fontsize=13, fontweight="bold")
        ax.text(i + 0.5, 0.66, f"{d:%d %b}", ha="center", va="center", color=txt, fontsize=9.5, alpha=0.9)
        if red:
            low = [f"{p} {r:g}" for p, r in zip(PRAYERS, row) if r is not None and 1 <= r < 2]
            ax.text(i + 0.5, 0.33, "\n".join(low), ha="center", va="center", color="white",
                    fontsize=10 if len(low) < 3 else 8.5, fontweight="bold")
        elif rated:
            vals = [r for r in rated if r != 0]
            if vals:
                ax.text(i + 0.5, 0.36, f"{sum(vals) / len(vals):.1f}", ha="center", va="center",
                        color="white", fontsize=16, fontweight="bold")
        else:
            ax.text(i + 0.5, 0.36, "no\nratings", ha="center", va="center", color=MUTED, fontsize=9.5)

    ax.set_xlim(0, 7)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")
    _save(fig, path)


def monthly_heatmap(days, grid, path):
    n = len(days)
    fig, ax = _fig(13, 3.4)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.70, bottom=0.10)
    vals = [r for row in grid for r in row if r is not None and r != 0]
    avg = sum(vals) / len(vals) if vals else None
    red = sum(any(r is not None and 1 <= r < 2 for r in row) for row in grid)
    _title(fig, f"{days[0]:%B %Y}",
           ("Average " + (f"{avg:.2f}" if avg is not None else "-"))
           + f"   |   {red} days with a 1   |   blank = not rated")

    for x, row in enumerate(grid):
        for y, r in enumerate(row):
            yy = 4 - y
            if r is None:
                ax.add_patch(FancyBboxPatch((x + 0.08, yy + 0.08), 0.84, 0.84,
                                            boxstyle="round,pad=0,rounding_size=0.15",
                                            fill=False, ec=EMPTY, lw=1))
                continue
            ax.add_patch(FancyBboxPatch((x + 0.08, yy + 0.08), 0.84, 0.84,
                                        boxstyle="round,pad=0,rounding_size=0.15", fc=color_for(r), ec="none"))
            ax.text(x + 0.5, yy + 0.5, f"{r:g}", ha="center", va="center", fontsize=7.5,
                    color=INK if r == 0 or 2.5 <= r < 4 else "white")

    ax.set_xlim(0, n)
    ax.set_ylim(0, 5)
    ax.set_aspect("equal")
    ax.set_yticks([4.5 - i for i in range(5)], PRAYERS, color=INK)
    ax.set_xticks([i + 0.5 for i in range(n)], [f"{d.day}" for d in days], fontsize=8, color=MUTED)
    ax.tick_params(length=0)
    _save(fig, path)
