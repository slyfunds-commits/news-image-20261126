#!/usr/bin/env python3
"""main.py — news-image front page for Thursday 26 November 2026.

Pure Python stdlib. Reads stories.json + numbers.json (a single source of
truth for every number on the page), renders a 1024x1024 front page with
draw.py, and writes it to MAKEFUN_OUTPUT_DIR/entry.png. Deterministic:
the same input bytes give the same output bytes (fixed data order, no
timestamps, no randomness). Runs twice byte-identical.

Layout, top to bottom: masthead band with the story count, the giant
mixed-case date, a one-line subheadline, region pills, a UTC timeline,
three big illustrated leads beside the numbers panel, two rows of five
small illustrated stories, the numbered briefs beside a dotted world map,
the date-check box, and the sources / how-sure footer.

A glyph spans 20 font units (cap 0..14, descender to 20), so a line of
text needs size * 20/14 * 1.05 of vertical room; anything tighter lets
descenders touch the next line's caps. Card heights are derived from
those line heights, and validate() fails loudly if any text would exceed
its line budget.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from draw import (Raster, put_text, para, wrap, measure, paint_scene,
                  paint_map, PAPER, INK, NAVY, NAVY2, RED, BLUE, TEAL,
                  GOLD, GREEN, GRAY, PALE, PALE2, WHITE, REGION_COLORS,
                  STATUS_COLORS)

W = 1024
H = 1024
MARGIN = 24
CW = W - 2 * MARGIN  # 976


def capsule(cv, x, y, w, h, color):
    """Capsule (rounded pill) in final px."""
    r = h / 2.0
    cv.box(x + r, y, w - 2 * r, h, color)
    cv.disc(x + r, y + r, r, color)
    cv.disc(x + w - r, y + r, r, color)


def chip(cv, x, y, label, color, size=11.0):
    """Status tag chip; returns its width."""
    tw = measure(label, size, bold=True) + 14
    capsule(cv, x, y, tw, size + 7, color)
    put_text(cv, label, x + 7, y + 3.5, size, WHITE, bold=True)
    return tw


def fit_size(s, max_size, min_size, max_w, bold=False):
    """Largest size in [min_size, max_size] whose width fits max_w."""
    size = max_size
    while size > min_size and measure(s, size, bold) > max_w:
        size -= 1
    return size


def load_data():
    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, "stories.json"), encoding="utf-8") as f:
        stories = json.load(f)
    with open(os.path.join(base, "numbers.json"), encoding="utf-8") as f:
        numbers = json.load(f)
    return stories, numbers


def masthead(cv, stories, y):
    cv.box(0, y, W, 34, NAVY)
    put_text(cv, "The world in one day", MARGIN, y + 8, 18, WHITE, bold=True)
    right = "%d stories · %d regions · all from this one day" % (
        stories["story_count"], len(stories["regions"]))
    put_text(cv, right, W - MARGIN, y + 10, 13, (232, 210, 140), align="right")
    return y + 34


def dateline(cv, stories, y):
    size = fit_size(stories["date"], 56, 40, CW, bold=True)
    put_text(cv, stories["date"], W / 2.0, y, size, NAVY, bold=True,
             align="center")
    return y + size + 6


def subhead(cv, stories, y):
    size = fit_size(stories["subheadline"], 18, 14, CW)
    if measure(stories["subheadline"], size) > CW:
        lines = wrap(stories["subheadline"], size, CW)
        for line in lines[:2]:
            put_text(cv, line, W / 2.0, y, size, RED, align="center")
            y += int(size * 1.5)
        return y
    put_text(cv, stories["subheadline"], W / 2.0, y, size, RED, align="center")
    return y + int(size * 1.5)


def region_row(cv, stories, y):
    x = MARGIN
    for reg in stories["regions"]:
        label = "%s %d" % (reg["name"], reg["count"])
        w = measure(label, 13, bold=True) + 18
        capsule(cv, x, y, w, 22, REGION_COLORS.get(reg["name"], GRAY))
        put_text(cv, label, x + 9, y + 4.5, 13, WHITE, bold=True)
        x += w + 6
    return y + 22


def utc_row(cv, stories, y):
    put_text(cv, "UTC", MARGIN, y, 13, RED, bold=True)
    parts = ["%s %s" % (item["time"], item["text"])
             for item in stories["timeline"]]
    line = "  ·  ".join(parts)
    put_text(cv, line, MARGIN + measure("UTC", 13, bold=True) + 10, y, 13, INK)
    return y + 18

def lead_card(cv, x, y, w, h, lead):
    cv.box(x, y, w, h, WHITE)
    cv.box(x, y, w, 2, REGION_COLORS.get(lead["region"], GRAY))
    paint_scene(cv, lead["icon"], x + 1, y + 3, w - 2, 88)
    cy = y + 98
    capsule(cv, x + 8, cy, 20, 20, NAVY)
    put_text(cv, str(lead["n"]), x + 18, cy + 4.5, 12, WHITE, bold=True,
             align="center")
    put_text(cv, lead["place"], x + 34, cy + 3.5, 13, INK, bold=True)
    cy += 26
    cy = para(cv, lead["headline"], x + 8, cy, 19, w - 16, INK,
              bold=True, line_h=27)
    cy += 4
    cy = para(cv, lead["body"], x + 8, cy, 12.5, w - 16, (50, 50, 50),
              line_h=18)
    put_text(cv, lead["source"], x + 8, y + h - 20, 10.5, GRAY)
    chip(cv, x + w - 8 - measure(lead["status"], 10.5, bold=True) - 14,
         y + h - 23, lead["status"], STATUS_COLORS[lead["status"]], size=10.5)


def numbers_box(cv, x, y, w, h, numbers):
    cv.box(x, y, w, h, NAVY2)
    put_text(cv, "The day in numbers", x + 12, y + 10, 15, WHITE, bold=True)
    cols = 2
    col_w = (w - 24) / cols
    for i, item in enumerate(numbers["items"]):
        cx = x + 12 + (i % cols) * col_w
        iy = y + 46 + (i // cols) * 58
        put_text(cv, item["value"], cx, iy, 20, WHITE, bold=True)
        put_text(cv, item["caption"], cx, iy + 28, 10.5, (200, 210, 230))
    put_text(cv, "Figures as reported on the day", x + 12, y + h - 18, 10,
             (170, 180, 200))


def mini_card(cv, x, y, w, h, story):
    cv.box(x, y, w, h, WHITE)
    cv.box(x, y, w, 2, REGION_COLORS.get(story["region"], GRAY))
    paint_scene(cv, story["icon"], x + 1, y + 3, w - 2, 44)
    cy = y + 52
    put_text(cv, "%d · %s" % (story["n"], story["place"]), x + 7, cy, 11,
             INK, bold=True)
    cy += 15
    cy = para(cv, story["headline"], x + 7, cy, 14, w - 14, INK,
              bold=True, line_h=21)
    cy += 3
    cy = para(cv, story["body"], x + 7, cy, 11, w - 14, (50, 50, 50),
              line_h=16)
    put_text(cv, story["source"], x + 7, y + h - 16, 10, GRAY)
    chip(cv, x + w - 7 - measure(story["status"], 10, bold=True) - 13,
         y + h - 19, story["status"], STATUS_COLORS[story["status"]], size=10)


def briefs_map(cv, stories, y, h):
    put_text(cv, "Also on %s" % stories["date_short"], MARGIN, y, 19, INK,
             bold=True)
    # Briefs: two columns on the left, one line each, region colour square.
    by = y + 28
    for i, brief in enumerate(stories["briefs"]):
        col = 0 if i < 8 else 1
        row = i % 8
        x = MARGIN + col * 312
        yy = by + row * 17
        cv.box(x, yy + 3, 8, 8, REGION_COLORS.get(brief["region"], GRAY))
        put_text(cv, "%d" % brief["n"], x + 12, yy, 12, RED, bold=True)
        put_text(cv, brief["text"], x + 34, yy, 12, INK)
    # Map on the right.
    mx = MARGIN + 2 * 312 + 8
    mw = W - MARGIN - mx
    put_text(cv, "Where it happened", mx, y, 16, INK, bold=True)
    put_text(cv, "pins = stories",
             mx + measure("Where it happened", 16, bold=True) + 8,
             y + 3, 11, GRAY)
    pins = [(p["n"], p["lon"], p["lat"]) for p in stories["map_pins"]]
    paint_map(cv, mx, y + 26, mw, h - 26, pins)


def datecheck_box(cv, stories, y, h):
    cv.box(MARGIN, y, CW, h, (255, 244, 240))
    cv.box(MARGIN, y, CW, 2, RED)
    cv.box(MARGIN, y + h - 2, CW, 2, RED)
    cv.box(MARGIN, y, 2, h, RED)
    cv.box(MARGIN + CW - 2, y, 2, h, RED)
    put_text(cv, "Date check", MARGIN + 8, y + 6, 14, RED, bold=True)
    text = ("Every story here happened or was first reported on Thursday "
            "26 November 2026 (UTC). Not that day: " +
            "; ".join(stories["date_check"]) + ".")
    para(cv, text, MARGIN + 96, y + 6, 12.5, CW - 104, INK, line_h=18)


def footline(cv, stories, y):
    put_text(cv, "How sure: %s" % stories["how_sure"], MARGIN, y, 11, GRAY)
    put_text(cv, stories["sources"] + " · Scenes are drawn illustrations, "
             "not photographs.", MARGIN, y + 14, 11, GRAY)

def render(stories, numbers):
    """Lay out the whole front page, top to bottom, and return the raster."""
    cv = Raster(W, H, ss=2, bg=PAPER)
    y = masthead(cv, stories, 0)
    y = dateline(cv, stories, y + 6)
    y = subhead(cv, stories, y + 2)
    y = region_row(cv, stories, y + 6)
    y = utc_row(cv, stories, y + 6)
    # Leads row: 3 cards + numbers panel.
    ly = y + 6
    lh = 244
    lead_w = 238
    gap = 8
    x = MARGIN
    for lead in stories["leads"]:
        lead_card(cv, x, ly, lead_w, lh, lead)
        x += lead_w + gap
    numbers_box(cv, x, ly, W - MARGIN - x, lh, numbers)
    # Small stories: 2 rows of 5.
    sw = 188
    sh = 158
    y = ly + lh + 6
    for row in range(2):
        x = MARGIN
        for story in stories["small"][row * 5:(row + 1) * 5]:
            mini_card(cv, x, y, sw, sh, story)
            x += sw + gap
        y += sh + 6
    # Briefs + map, then date check, then footer.
    briefs_map(cv, stories, y, 168)
    y += 168 + 6
    datecheck_box(cv, stories, y, 48)
    y += 48 + 6
    footline(cv, stories, y)
    y += 28
    assert y <= H, "layout overflow: %d > %d" % (y, H)
    return cv


def validate(stories, numbers):
    """Fail loudly if any text would overflow its slot (line budgets)."""
    total = (len(stories["leads"]) + len(stories["small"]) +
             len(stories["briefs"]))
    assert total == stories["story_count"], "story count mismatch"
    region_totals = {}
    for s in stories["leads"] + stories["small"] + stories["briefs"]:
        region_totals[s["region"]] = region_totals.get(s["region"], 0) + 1
    for reg in stories["regions"]:
        assert region_totals.get(reg["name"], 0) == reg["count"], \
            "region count mismatch: %s" % reg["name"]
    assert sum(region_totals.values()) == total
    for lead in stories["leads"]:
        assert len(wrap(lead["headline"], 19, 238 - 16, bold=True)) <= 2, \
            "lead headline too long: %s" % lead["headline"]
        assert len(wrap(lead["body"], 12.5, 238 - 16)) <= 2, \
            "lead body too long: %s" % lead["body"]
    for s in stories["small"]:
        assert len(wrap(s["headline"], 14, 188 - 14, bold=True)) <= 2, \
            "small headline too long: %s" % s["headline"]
        assert len(wrap(s["body"], 11, 188 - 14)) <= 2, \
            "small body too long: %s" % s["body"]
    for b in stories["briefs"]:
        assert measure(b["text"], 12) <= 262, \
            "brief too long: %s" % b["text"]
    for item in numbers["items"]:
        assert measure(item["value"], 20, bold=True) <= 100, \
            "number value too wide: %s" % item["value"]
        assert measure(item["caption"], 10.5) <= 100, \
            "number caption too wide: %s" % item["caption"]
    assert measure(stories["date"], 40, bold=True) <= CW, "date too wide"
    assert len(stories["date_check"]) >= 3, "date check needs exclusions"
    dc = ("Every story here happened or was first reported on Thursday "
          "26 November 2026 (UTC). Not that day: " +
          "; ".join(stories["date_check"]) + ".")
    assert len(wrap(dc, 12.5, CW - 104)) <= 2, "date check too long"


def main():
    stories, numbers = load_data()
    validate(stories, numbers)
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    cv = render(stories, numbers)
    with open(os.path.join(out_dir, "entry.png"), "wb") as f:
        f.write(cv.png())


if __name__ == "__main__":
    main()
