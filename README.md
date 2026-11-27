# Thursday, 26 November 2026 — the world in one image

[![make.fun · news-image-20261126](https://make.fun/badge/news-image-20261126.svg)](https://make.fun/bounty/news-image-20261126?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261126)
[![rank](https://make.fun/badge/news-image-20261126/slyfunds-commits/news-image-20261126/rank.svg)](https://make.fun/bounty/news-image-20261126/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261126)
[![reward](https://make.fun/badge/news-image-20261126/slyfunds-commits/news-image-20261126/reward.svg)](https://make.fun/bounty/news-image-20261126?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261126)

A program that sums up Thursday 26 November 2026's world news in one
1024×1024 front page: masthead + story count, the giant mixed-case date,
a region strip, a UTC timeline, three big illustrated leads beside the
day-in-numbers panel, ten small illustrated stories, numbered briefs
beside a dotted world map, a date-check box, and the sources / how-sure
footer. Every number on the page is rendered from one table
(`numbers.json`); every story carries a source and a status tag
(Reported / Confirmed / Claim / Ongoing). Scenes are drawn illustrations,
not photographs.

## How it works

`main.py` (Python 3.13, standard library only) reads `stories.json` and
`numbers.json`, renders the page with `draw.py` — a pure-stdlib 2D
renderer with a hand-built stroke font, flat vector scenes, and a dotted
world map computed from continent polygons — and writes the PNG to
`$MAKEFUN_OUTPUT_DIR/entry.png` (default `/output`). The render is
deterministic: the same data always produces the same bytes.

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

## Status

✅ **Filled with real 26 November 2026 news.** Every story, number,
timeline entry and date-check item is the day's real verified news
(two outlets per story, checked the morning of 27 November 2026),
rendered from `stories.json` + `numbers.json`.
Before submit the page is rendered at 300px wide and every line is
read aloud against the zero-mistake checklist.

## About

Built for the [news-image-20261126 bounty](https://make.fun/bounty/news-image-20261126)
on [make.fun](https://make.fun/r/t2zg4r38).
