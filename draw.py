"""Fresh front-page renderer for the 26 November 2026 news image.

Pure standard library: a small supersampled raster, a hand-built stroke
font, flat vector scenes and a dotted world map. Reads the day's stories
from data files (never from here) and paints one 1024x1024 page.

Design notes (all my own):
- Glyphs live on a 10-wide by 14-tall unit grid: cap top y=0, baseline
  y=11, descender floor y=13. One vertical unit is size/11.5 pixels, so
  cap height is about 0.96*size; one horizontal unit is size/9 * SX
  pixels, so letters stay tall and narrow like a condensed face.
- Text width is the sum of glyph advances plus a small gap between
  neighbours (0.05 * size); bold only thickens strokes, never widths.
- The raster is supersampled (default 2x) and downsampled on export, so
  edges stay smooth without any extra dependency.
"""

import math
import struct
import zlib

# ---------------------------------------------------------------- palette
# Colours sampled from the target front page (the rendered reference PNG).
PAPER = (248, 243, 231)   # warm newsprint cream
INK = (20, 24, 38)        # near-black text ink
NIGHT = (20, 24, 38)      # darkest scene tone
NAVY = (14, 28, 60)       # masthead band and giant date
NAVY2 = (24, 44, 88)      # numbers-panel background
BLUE = (32, 86, 156)      # reported blue
RED = (170, 28, 24)       # subheadline red and date-check red
GOLD = (184, 130, 24)     # claim gold
GREEN = (44, 120, 62)     # africa green
GRAY = (110, 110, 108)    # world grey
SKY = (190, 210, 232)     # pale daytime sky
SAND = (232, 214, 170)    # warm sand tone
TEAL = (30, 100, 150)     # mid sky blue
WHITE = (255, 255, 255)
PALE = (232, 238, 244)    # pale blue-grey fill
PALE2 = (237, 223, 197)   # pale warm fill

# Horizontal squeeze applied to every glyph (see module docstring).
SX = 0.74

REGION_COLORS = {
    "Europe": (32, 86, 156),
    "Middle East": (170, 28, 24),
    "Africa": (44, 120, 62),
    "Asia": (184, 130, 24),
    "Americas": (200, 80, 40),
    "Oceania": (24, 44, 88),
    "World": (110, 110, 108),
}

STATUS_COLORS = {
    "Reported": (32, 86, 156),
    "Claim": (184, 130, 24),
    "Confirmed": (44, 120, 62),
    "Ongoing": (120, 90, 160),
}

# ------------------------------------------------------------------- font
# Each glyph: "advance|stroke;stroke" where a stroke is "x,y x,y ...".
# Grid: x 0..10, y 0..14, cap top 0, x-height top 4, baseline 11.
GLYPHS = {
    " ": "3.2|",
    "!": "3|1.5,0 1.5,8;1.5,10 1.5,11",
    '"': "3.6|1,0 1,2.5;2.6,0 2.6,2.5",
    "$": "7|3.5,0 3.5,11;5.5,1.5 4,0 2,0 1,1.5 1,4 2.5,5.5 4.5,6.5 6,8 6,9.5 4.5,11 2.5,11 1,10",
    "%": "8|0.8,2 1.8,0.5 3.2,1 3.2,3 2,4.5 0.8,4;5.5,8 6.5,6.5 7,7.5 7,9.5 6,11 5,10.5;6.8,0.5 0.5,10.8",
    "&": "7|5.5,0 4,0.5 2.5,2 2,4 3,6 5,7.5 6,9 5,11 3,11 1.5,9.5;2,4 0.8,5.5 0.8,8 2,10 4,10.5",
    "'": "2.6|1.3,0 1.3,2.5",
    "(": "4|3,0 1.5,2.5 1,5.5 1.5,8.5 3,11",
    ")": "4|1,0 2.5,2.5 3,5.5 2.5,8.5 1,11",
    "+": "7|3.5,2 3.5,9;0.8,5.5 6.2,5.5",
    ",": "3|1.5,9.5 1.5,11 1,12.5 0.3,13",
    "-": "5|0.8,7 5,7",
    ".": "3|1.5,10 1.5,11",
    "/": "5|4.5,0 0.8,11",
    "0": "7|1.5,1 3.5,0 5.5,1 6.2,3 6.2,8 5.5,10.5 3.5,11 1.5,10.5 0.8,8 0.8,3 1.5,1",
    "1": "7|4.5,0 3.5,2 3.5,11;1.5,11 5.5,11",
    "2": "7|1,3 1,1 3.5,0 6,1 6,4 1,11 6,11",
    "3": "7|1,1 3.5,0 6,1 6,4 3.5,5.5;3.5,5.5 6,6 6,9 3.5,11 1,10",
    "4": "7|5,0.5 5,11;0.8,8 6.2,8;0.8,8 5,0.5",
    "5": "7|6,0 1,0 1,5 4,5 6,6.5 6,9 3.5,11 1,10",
    "6": "7|5.5,0 3.5,0 1.5,2 1,5 1,8 2,10.5 4,11 5.5,10 6,8 5,6 3,6",
    "7": "7|1,0 6,0 3,11;1.5,5.5 4,5.5",
    "8": "7|2,0.5 5,0.5 6,2 5.5,4 4,5 2,5.5 1,7 1.5,9.5 3.5,11 5,10.5 6,9 5.5,7",
    "9": "7|1,8 1,5 2,1 4,0 5.5,1 6,3 5.5,6 3,6;5,6 6,9 4,11 2,10.5",
    ":": "3|1.5,4 1.5,5.5;1.5,9.5 1.5,11",
    ";": "3|1.5,4 1.5,5.5;1.5,9.5 1.5,11 1,12.5 0.3,13",
    "=": "7|0.8,4 6.2,4;0.8,7.5 6.2,7.5",
    "?": "7|1.5,3 1.5,1.5 3,0 5,0.5 6,2 5.5,4 3.5,5.5 3.5,7;3.5,9.5 3.5,11",
    "A": "7.4|0.5,11 3.7,0 6.9,11;2.2,7 5.2,7",
    "B": "7.4|0.5,11 0.5,0;0.5,0 4.5,0 6.5,1.5 6.5,4 4.5,5.5 0.5,5.5;4.5,5.5 6.5,6.5 6.5,9 4.5,11 0.5,11",
    "C": "7.4|6.5,2.5 5,0.5 2.5,0 1,2 0.5,5.5 1,9 2.5,11 5,11 6.5,9",
    "D": "7.4|0.5,11 0.5,0;0.5,0 4,0 6.5,2 6.9,5.5 6.5,9 4,11 0.5,11",
    "E": "7.4|0.5,11 0.5,0 6.5,0;0.5,5.5 5,5.5;0.5,11 6.5,11",
    "F": "6.2|0.5,11 0.5,0 5.4,0;0.5,5.5 4.2,5.5",
    "G": "7.4|6.5,2.5 5,0.5 2.5,0 1,2 0.5,5.5 1,9 2.5,11 5,11 6.5,9 6.5,7 4,7",
    "H": "7.4|0.5,0 0.5,11;6.9,0 6.9,11;0.5,5.5 6.9,5.5",
    "I": "3.8|0.6,0 3.2,0;1.9,0 1.9,11;0.6,11 3.2,11",
    "J": "5.2|1,0 4.4,0;4.4,0 4.4,8 3.6,10.5 2,11 1,10",
    "K": "7.4|0.5,0 0.5,11;6.9,0 0.5,6;2,4.5 6.9,11",
    "L": "6.0|0.5,0 0.5,11 5.5,11",
    "M": "7.4|0.5,11 0.5,0 3.7,7 6.9,0 6.9,11",
    "N": "7.4|0.5,11 0.5,0 6.9,11 6.9,0",
    "O": "7.4|2,0.5 5,0.5 6.7,2.5 6.9,5.5 6.7,8.5 5,10.8 2,10.8 0.7,8.5 0.5,5.5 0.7,2.5",
    "P": "7.4|0.5,11 0.5,0;0.5,0 4.5,0 6.5,1.5 6.5,4 4.5,5.5 0.5,5.5",
    "Q": "7.4|2,0.5 5,0.5 6.7,2.5 6.9,5.5 6.7,8.5 5,10.8 2,10.8 0.7,8.5 0.5,5.5 0.7,2.5;4.5,8 7,11.5",
    "R": "7.4|0.5,11 0.5,0;0.5,0 4.5,0 6.5,1.5 6.5,4 4.5,5.5 0.5,5.5;3.5,5.5 6.9,11",
    "S": "7.4|6,1.5 4.5,0 2,0 0.8,1.5 0.8,4 2.5,5.5 5,6.5 6.5,8 6.5,9.5 5,11 2.5,11 1,10",
    "T": "6.4|0.5,0 5.9,0;3.2,0 3.2,11",
    "U": "7.4|0.5,0 0.5,8 1.5,10.5 3.7,11 5.9,10.5 6.9,8 6.9,0",
    "V": "7.4|0.5,0 3.7,11 6.9,0",
    "W": "9.6|0.5,0 2,11 4.8,3 7.6,11 9.1,0",
    "X": "7.4|0.5,0 6.9,11;6.9,0 0.5,11",
    "Y": "7.4|0.5,0 3.7,5.5 6.9,0;3.7,5.5 3.7,11",
    "Z": "7.4|0.5,0 6.9,0 0.5,11 6.9,11",
    "a": "6.6|6,4.5 5,4 2.5,4 1,5.5 1,8 2,10.5 4,11 5.5,10 6,8 6,4.5;6,4.5 6,11",
    "b": "6.6|1,0 1,11;1,8 2.5,9.8 4,9.8 5.5,8 6,6.5 5.5,5 4,4 2.5,4 1,5.5",
    "c": "6.2|5.6,5.5 4.2,4 2.4,4 1,5.5 0.8,8 1.9,10.5 3.8,11 5.6,10",
    "d": "6.6|6,0 6,11;6,8 4.5,9.8 2.5,9.8 1,8 0.8,6.5 2,4.5 4,4 6,5",
    "e": "6.6|1,8 1.5,5.5 3,4 5,4 6,5.5 6,7 4,8.5 2,8.5 1,7.5;1,8 6,8",
    "f": "4.8|2.6,11 2.6,2.5 3.4,0.5 4.6,0;0.8,4.5 4.6,4.5",
    "g": "6.4|1,8 1.5,5.5 2.9,4 4.7,4 5.6,5.5 5.6,8 4.3,10.5 2.4,10.5 1,9;5.6,8 5.2,11.5 3.8,13 2,13",
    "h": "6.6|1,0 1,11;1,7 2.5,4.5 4.5,4.5 6,6 6,11",
    "i": "2.6|1.3,4.5 1.3,11;1.3,0.8 1.3,2",
    "j": "2.6|2,0.8 2,2;2,4.5 2,11 1.5,12.5 0.5,13",
    "k": "6.2|1,0 1,11;5.6,4 1,7;2.1,5.8 5.6,11",
    "l": "2.6|1.3,0 1.3,11",
    "m": "9.6|1,11 1,4.5;1,7 2,4.5 3.5,4.5 4.8,6 4.8,11;4.8,7 5.8,4.5 7.3,4.5 8.6,6 8.6,11",
    "n": "6.6|1,11 1,4.5;1,7 2.5,4.5 4.5,4.5 6,6 6,11",
    "o": "6.6|2,4.5 4,4 5.5,5.5 6,8 5,10.5 3,11 1.5,10 0.8,8 1.5,5.5",
    "p": "6.6|1,4.5 1,13;1,8 2.5,9.8 4,9.8 5.5,8 6,6.5 5.5,5 4,4 2.5,4 1,5.5",
    "q": "6.6|6,4.5 6,13;6,8 4.5,9.8 3,9.8 1.5,8 1,6.5 1.5,5 3,4 4.5,4 6,5.5",
    "r": "5.2|1,11 1,4.5;1,7 2.2,4.5 3.6,4.5 4.8,5.5",
    "s": "6.2|5.2,5.5 3.8,4 1.9,4 1,5.5 1,7 2.4,8.5 4.2,9 5.4,10 5.2,10.8 3.8,11 1.9,11 1,10",
    "t": "4.8|2,1.5 2.8,0.5 2.8,11;0.8,4.5 4.6,4.5",
    "u": "6.6|1,4.5 1,8.5 2,10.5 3.5,11 5,10.5 6,8.5 6,4.5",
    "v": "6.6|0.8,4.5 3.5,11 6.2,4.5",
    "w": "9.6|0.8,4.5 2,11 4.8,6 7.6,11 8.8,4.5",
    "x": "6.6|0.8,4.5 6,11;6,4.5 0.8,11",
    "y": "6.6|0.8,4.5 3.5,11 6.2,4.5;3.5,11 2.8,13",
    "z": "6.6|0.8,4.5 6,4.5 0.8,11 6,11",
    "°": "4|1.5,0.5 2.5,0 3.2,1 3,2.5 2,3.2 1,2.5 0.8,1",
    "·": "3|1.5,6.5 1.5,8",
    "×": "6|1,2 5,9;5,2 1,9",
    "–": "6|0.8,7 5.5,7",
    "—": "8|0.8,7 7.2,7",
    "‘": "2.6|1.3,0 0.8,2.5",
    "’": "2.6|1.3,0 1.8,2.5",
    "“": "5|1,0 0.8,2.5;3.5,0 3.3,2.5",
    "”": "5|1,0 1.3,2.5;3.5,0 3.8,2.5",
    "•": "4|1,6 2,5 3,6 3,8 2,9 1,8",
    "−": "6|0.8,5.5 5.5,5.5",
}

_FALLBACK = "?"


def _parse_glyphs():
    """Turn the GLYPHS strings into (advance, strokes) point lists."""
    parsed = {}
    for ch, spec in GLYPHS.items():
        adv_txt, _, strokes_txt = spec.partition("|")
        strokes = []
        if strokes_txt:
            for stroke_txt in strokes_txt.split(";"):
                pts = []
                for pair in stroke_txt.split():
                    xs, _, ys = pair.partition(",")
                    pts.append((float(xs), float(ys)))
                if len(pts) >= 2:
                    strokes.append(tuple(pts))
                elif len(pts) == 1:
                    strokes.append((pts[0], pts[0]))
        parsed[ch] = (float(adv_txt), tuple(strokes))
    return parsed


PARSED = _parse_glyphs()

# ------------------------------------------------------- low-level drawing
# All helpers work on a flat RGB bytearray in supersampled pixel space:
# buf is W*H*3 bytes, row-major, no padding. Coordinates are floats in
# that space; callers scale logical coordinates by the raster's ss first.


def _hspan(buf, W, H, y, x0, x1, rgb):
    """Fill one horizontal run [x0, x1) on row y, clipped to the canvas."""
    if y < 0 or y >= H:
        return
    if x0 < 0:
        x0 = 0
    if x1 > W:
        x1 = W
    if x1 <= x0:
        return
    r, g, b = rgb
    base = (y * W + x0) * 3
    n = x1 - x0
    buf[base:base + n * 3] = bytes((r, g, b)) * n


def _disc_into(buf, W, H, cx, cy, rad, rgb):
    """Fill a disc centred at (cx, cy) with radius rad (pixel units)."""
    if rad <= 0:
        return
    r2 = rad * rad
    y0 = int(math.floor(cy - rad))
    y1 = int(math.ceil(cy + rad))
    for y in range(y0, y1 + 1):
        dy = y + 0.5 - cy
        rest = r2 - dy * dy
        if rest < 0:
            continue
        dx = math.sqrt(rest)
        _hspan(buf, W, H, y, int(math.ceil(cx - dx)), int(math.floor(cx + dx)) + 1, rgb)


def _poly_into(buf, W, H, pts, rgb):
    """Scanline-fill a polygon given as [(x, y), ...] in pixel units."""
    if len(pts) < 3:
        return
    ys = [p[1] for p in pts]
    y0 = int(math.floor(min(ys)))
    y1 = int(math.ceil(max(ys)))
    n = len(pts)
    for y in range(y0, y1 + 1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            x1, y1p = pts[i]
            x2, y2p = pts[(i + 1) % n]
            if (y1p <= yc < y2p) or (y2p <= yc < y1p):
                t = (yc - y1p) / (y2p - y1p)
                xs.append(x1 + t * (x2 - x1))
        if len(xs) < 2:
            continue
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            _hspan(buf, W, H, y, int(math.ceil(xs[k])), int(math.floor(xs[k + 1])) + 1, rgb)


def _stroke_into(buf, W, H, pts, thick, rgb):
    """Draw a thick polyline through pts (pixel units, round caps)."""
    if not pts:
        return
    if len(pts) == 1:
        _disc_into(buf, W, H, pts[0][0], pts[0][1], thick / 2.0, rgb)
        return
    half = thick / 2.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 0.001:
            _disc_into(buf, W, H, x1, y1, half, rgb)
            continue
        nx, ny = -dy / length * half, dx / length * half
        _poly_into(buf, W, H, [
            (x1 + nx, y1 + ny), (x2 + nx, y2 + ny),
            (x2 - nx, y2 - ny), (x1 - nx, y1 - ny),
        ], rgb)
        _disc_into(buf, W, H, x1, y1, half, rgb)
        _disc_into(buf, W, H, x2, y2, half, rgb)


def _png_bytes(w, h, rgb):
    """Encode flat RGB bytes as a PNG (filter 0, deterministic)."""
    stride = w * 3
    raw = bytearray((stride + 1) * h)
    for y in range(h):
        raw[y * (stride + 1)] = 0
        raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)] = rgb[y * stride:(y + 1) * stride]

    def chunk(typ, data):
        out = struct.pack(">I", len(data)) + typ + data
        return out + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + chunk(b"IEND", b"")
    )


class Raster:
    """A supersampled RGB canvas in logical coordinates."""

    def __init__(self, w, h, ss=2, bg=(248, 243, 231)):
        self.w = int(w)
        self.h = int(h)
        self.ss = int(ss) if ss else 1
        self.sw = self.w * self.ss
        self.sh = self.h * self.ss
        row = bytes(bg) * self.sw
        self.buf = bytearray(row * self.sh)

    def _px(self, v):
        return v * self.ss

    def fill(self, color):
        row = bytes(color) * self.sw
        self.buf[:] = row * self.sh

    def box(self, x, y, w, h, color):
        x0 = int(math.floor(self._px(x)))
        y0 = int(math.floor(self._px(y)))
        x1 = int(math.ceil(self._px(x + w)))
        y1 = int(math.ceil(self._px(y + h)))
        for yy in range(max(0, y0), min(self.sh, y1)):
            _hspan(self.buf, self.sw, self.sh, yy, max(0, x0), min(self.sw, x1), color)

    def disc(self, cx, cy, r, color):
        _disc_into(self.buf, self.sw, self.sh,
                   self._px(cx), self._px(cy), self._px(r), color)

    def poly(self, points, color):
        scaled = [(self._px(px), self._px(py)) for px, py in points]
        _poly_into(self.buf, self.sw, self.sh, scaled, color)

    def seg(self, x1, y1, x2, y2, w, color):
        thick = max(self._px(w), 1.0)
        pts = [(self._px(x1), self._px(y1)), (self._px(x2), self._px(y2))]
        _stroke_into(self.buf, self.sw, self.sh, pts, thick, color)

    def sample(self):
        """Downsampled RGB bytes (w*h*3), averaging each ss x ss block."""
        ss = self.ss
        sw, sh = self.sw, self.sh
        buf = self.buf
        out = bytearray(self.w * self.h * 3)
        if ss == 1:
            out[:] = buf
            return bytes(out)
        for oy in range(self.h):
            y0 = oy * ss
            orow = oy * self.w * 3
            for ox in range(self.w):
                x0 = ox * ss
                sr = sg = sb = 0
                for dy in range(ss):
                    base = ((y0 + dy) * sw + x0) * 3
                    for dx in range(ss):
                        i = base + dx * 3
                        sr += buf[i]
                        sg += buf[i + 1]
                        sb += buf[i + 2]
                n = ss * ss
                o = orow + ox * 3
                out[o] = sr // n
                out[o + 1] = sg // n
                out[o + 2] = sb // n
        return bytes(out)

    def png(self):
        return _png_bytes(self.w, self.h, self.sample())

# --------------------------------------------------------------------- text
# One vertical grid unit is size/9 pixels; cap height is 11 units, so a
# size-S glyph stands about 1.22*S tall with a short descender below the
# baseline at unit 11. Horizontal units are squeezed by SX.
_GAP = 0.05          # extra space between neighbours, in units of size
_LINE_H = 1.28       # default line height, in units of size
_GLYPH_RUNS = {}     # (char, size, bold, ss) -> ((dy, x0, x1), ...)


def _adv_units(ch):
    entry = PARSED.get(ch)
    if entry is None:
        entry = PARSED[_FALLBACK]
    return entry[0]


def _char_advance(ch, size):
    return _adv_units(ch) * size / 9.0 * SX


def measure(s, size, bold=False):
    """Width in logical pixels of s at the given size (bold is as wide)."""
    if not s:
        return 0.0
    total = 0.0
    for ch in s:
        total += _char_advance(ch, size)
    total += max(0, len(s) - 1) * size * _GAP
    return total


def _split_long_word(word, size, max_w, bold=False):
    """Break one over-wide word into chunks that each fit max_w."""
    chunks = []
    cur = ""
    for ch in word:
        trial = cur + ch
        if cur and measure(trial, size, bold) > max_w:
            chunks.append(cur)
            cur = ch
        else:
            cur = trial
    if cur:
        chunks.append(cur)
    return chunks


def wrap(s, size, max_w, bold=False):
    """Greedy word wrap; returns a list of lines (never a trailing blank)."""
    if not s:
        return []
    lines = []
    for word in s.split(" "):
        if not word:
            continue
        if measure(word, size, bold) > max_w:
            pieces = _split_long_word(word, size, max_w, bold)
            for piece in pieces:
                if lines and measure(lines[-1] + " " + piece, size, bold) <= max_w:
                    lines[-1] = lines[-1] + " " + piece
                else:
                    lines.append(piece)
            continue
        if lines and measure(lines[-1] + " " + word, size, bold) <= max_w:
            lines[-1] = lines[-1] + " " + word
        else:
            lines.append(word)
    return lines


def _glyph_runs(ch, size, bold, ss):
    """Horizontal ink runs of one glyph, in supersampled pixels.

    Returns ((dy, x0, x1), ...) relative to the glyph cell's top-left,
    where the cell is advance-wide and 14 grid units tall. Cached.
    """
    key = (ch, round(float(size), 3), bool(bold), ss)
    cached = _GLYPH_RUNS.get(key)
    if cached is not None:
        return cached
    adv, strokes = PARSED.get(ch, PARSED[_FALLBACK])
    scale_v = size / 11.5
    scale_h = size / 9.0 * SX
    cell_w = max(1, int(math.ceil(adv * scale_h * ss)) + 2)
    cell_h = max(1, int(math.ceil(14 * scale_v * ss)) + 2)
    buf = bytearray(cell_w * cell_h * 3)
    thick = max(1.0, size * (0.17 if bold else 0.10) * ss)
    for stroke in strokes:
        pts = [(gx * scale_h * ss + 1.0, gy * scale_v * ss + 1.0)
               for gx, gy in stroke]
        _stroke_into(buf, cell_w, cell_h, pts, thick, (255, 255, 255))
    runs = []
    for y in range(cell_h):
        row = y * cell_w * 3
        x = 0
        while x < cell_w:
            if buf[row + x * 3]:
                x0 = x
                while x < cell_w and buf[row + x * 3]:
                    x += 1
                runs.append((y, x0, x))
            else:
                x += 1
    runs = tuple(runs)
    _GLYPH_RUNS[key] = runs
    return runs


def put_text(raster, s, x, y_top, size, color, bold=False, align="left"):
    """Draw s with its top at y_top; returns the width drawn."""
    if not s:
        return 0.0
    width = measure(s, size, bold)
    if align == "center":
        pen = x - width / 2.0
    elif align == "right":
        pen = x - width
    else:
        pen = x
    ss = raster.ss
    y0 = int(round(y_top * ss))
    gap = size * _GAP
    for ch in s:
        if ch == "\n":
            ch = " "
        runs = _glyph_runs(ch, size, bold, ss)
        x0 = int(round(pen * ss))
        for dy, rx0, rx1 in runs:
            _hspan(raster.buf, raster.sw, raster.sh, y0 + dy,
                   x0 + rx0, x0 + rx1, color)
        pen += _char_advance(ch, size) + gap
    return width


def para(raster, s, x, y_top, size, max_w, color, bold=False, line_h=None):
    """Draw a wrapped paragraph; returns the y just below its last line."""
    if line_h is None:
        line_h = size * _LINE_H
    lines = wrap(s, size, max_w, bold)
    y = y_top
    for line in lines:
        put_text(raster, line, x, y, size, color, bold)
        y += line_h
    return y

# ------------------------------------------------------------ dotted world
# A hand-drawn land mask: 60 columns of 6 degrees longitude, 30 rows of 6
# degrees latitude (row 0 is 84-90N, row 29 is 84-90S). '#' is land.
# Drawn from memory of the continents' shapes; Antarctica left blank,
# as on the reference page.
LAND = (
    "....................###.....................................",
    "...............############.................................",
    ".......########....####................#.....#####..........",
    "..###############...###.......##.#########################..",
    "...###############........##.#############################..",
    "....###############..........#############################..",
    "...........#########.........############################...",
    "...........##########.......#############################...",
    "............#########.......#############################...",
    ".............#########......###########################.....",
    ".............#####..#.......#############.#########.........",
    "..............####.###......#########.###..########.........",
    "...............###...........########.......#.#######.......",
    "...............#####..........#######..........#######......",
    "...............######.........######.............########...",
    "...............######.........######..............#######...",
    "...............######.........#####................####.....",
    "...............#####..........####..#.............######....",
    "...............#####..........####..#.............#######...",
    "...............####...........####................######....",
    "................###...........###..................####..#..",
    "................##..................................###..#..",
    "................#........................................#..",
    "................#...........................................",
    "............................................................",
    "............................................................",
    "............................................................",
    "............................................................",
    "............................................................",
    "............................................................",
)

# Coarse continent outlines in (lon, lat) pairs, for callers that want
# polygons instead of the dot grid. Rough on purpose; the dots carry the
# map, these are only a fallback shape.
CONTINENTS = [
    [(-168, 66), (-140, 70), (-125, 72), (-110, 68), (-95, 69), (-85, 66),
     (-80, 62), (-76, 58), (-70, 45), (-75, 35), (-80, 26), (-85, 20),
     (-90, 15), (-95, 18), (-105, 22), (-115, 28), (-125, 40), (-125, 48),
     (-135, 58), (-150, 60), (-165, 60)],
    [(-58, 64), (-45, 60), (-32, 68), (-22, 70), (-30, 76), (-45, 80),
     (-58, 76), (-60, 70)],
    [(-80, 10), (-75, 5), (-70, -5), (-60, -10), (-50, -5), (-40, -10),
     (-35, -15), (-40, -25), (-48, -28), (-55, -35), (-60, -40),
     (-65, -45), (-68, -52), (-70, -45), (-72, -35), (-72, -20),
     (-78, -10), (-80, 0)],
    [(-10, 36), (-9, 43), (-2, 48), (0, 50), (5, 53), (8, 57), (12, 55),
     (18, 56), (21, 59), (24, 60), (28, 62), (30, 70), (25, 71), (18, 69),
     (12, 66), (5, 60), (-2, 57), (-5, 50), (-8, 43), (-10, 38)],
    [(-17, 15), (-10, 30), (0, 35), (10, 37), (20, 32), (30, 31),
     (35, 28), (40, 15), (43, 11), (48, 10), (51, 10), (48, 0), (42, -5),
     (40, -15), (35, -25), (32, -30), (28, -34), (20, -35), (15, -30),
     (12, -18), (12, -5), (8, 4), (-8, 5), (-15, 11)],
    [(35, 36), (43, 38), (48, 30), (50, 26), (55, 25), (58, 22), (55, 17),
     (48, 15), (43, 12), (40, 20), (35, 28)],
    [(30, 70), (50, 72), (70, 72), (90, 75), (110, 73), (130, 72),
     (150, 70), (170, 67), (178, 65), (170, 60), (160, 60), (150, 60),
     (140, 55), (130, 50), (120, 50), (110, 50), (100, 50), (90, 50),
     (80, 50), (70, 52), (60, 55), (50, 60), (40, 65), (35, 68)],
    [(68, 23), (72, 20), (76, 8), (80, 10), (80, 18), (85, 20), (88, 22),
     (90, 24), (88, 26), (80, 28), (75, 27), (70, 25)],
    [(98, 16), (100, 8), (103, 2), (105, -2), (108, -5), (112, -7),
     (115, -8), (118, -10), (120, -5), (122, 0), (125, 2), (128, 0),
     (130, -2), (132, -4), (135, -5), (138, -8), (141, -8), (140, -2),
     (138, 2), (135, 5), (132, 8), (130, 10), (128, 12), (125, 15),
     (122, 18), (120, 20), (118, 22), (115, 20), (112, 18), (108, 16),
     (105, 15), (102, 14), (100, 16)],
    [(113, -22), (114, -30), (115, -35), (120, -34), (125, -32),
     (130, -32), (135, -35), (140, -38), (145, -38), (150, -37),
     (153, -32), (153, -27), (150, -22), (146, -19), (142, -15),
     (140, -12), (136, -12), (132, -11), (128, -14), (124, -16),
     (120, -20), (116, -20)],
    [(166, -34), (168, -38), (170, -42), (172, -44), (174, -41),
     (176, -38), (174, -36), (170, -35)],
    [(130, 31), (132, 33), (135, 34), (137, 35), (139, 35), (140, 38),
     (141, 41), (142, 44), (140, 45), (138, 42), (136, 38), (133, 35),
     (131, 33)],
]


def _lonlat(lon, lat, x, y, w, h):
    """Equirectangular projection of one lon/lat into a map rectangle."""
    px = x + (lon + 180.0) / 360.0 * w
    py = y + (90.0 - lat) / 180.0 * h
    return px, py


def paint_map(raster, x, y, w, h, pins, dot_color=(70, 80, 100),
              pin_color=(170, 28, 24)):
    """Dot the land grid, then drop numbered pins at their true places.

    pins is a list of (n, lon, lat) tuples (dicts with lat/lon/n also
    work). Pin numbers are drawn in white, centred on their disc.
    """
    cols = len(LAND[0])
    rows = len(LAND)
    step_x = w / float(cols)
    step_y = h / float(rows)
    step = min(step_x, step_y)
    dot_r = max(1.2, step * 0.36)
    for r in range(rows):
        line = LAND[r]
        cy = y + (r + 0.5) * step_y
        for c in range(cols):
            if line[c] == "#":
                cx = x + (c + 0.5) * step_x
                raster.disc(cx, cy, dot_r, dot_color)
    pin_r = max(4.0, w * 0.032)
    for pin in pins or []:
        if isinstance(pin, dict):
            lat, lon, n = pin.get("lat"), pin.get("lon"), pin.get("n")
        else:
            n, lon, lat = pin[0], pin[1], pin[2]
        px, py = _lonlat(lon, lat, x, y, w, h)
        raster.disc(px, py, pin_r, pin_color)
        label = str(n)
        size = pin_r * 1.1
        put_text(raster, label, px, py - size * 0.48, size, WHITE,
                 bold=True, align="center")

# ------------------------------------------------------------------- scenes
# Every scene is drawn from fractions of its own rectangle, so the same
# painter works for a wide lead strip and a small card strip. Skies are
# flat, shapes are few and bold, nothing photographic.

SCENES = {
    "tanker": {"sky": SKY, "ground": TEAL, "motif": "ship"},
    "drone": {"sky": NIGHT, "ground": NIGHT, "motif": "quad"},
    "parade": {"sky": SAND, "ground": PALE2, "motif": "balloon"},
    "city": {"sky": TEAL, "ground": NIGHT, "motif": "towers"},
    "energy": {"sky": PALE, "ground": SAND, "motif": "refinery"},
    "chart": {"sky": PAPER, "ground": PAPER, "motif": "bars"},
    "flag": {"sky": SKY, "ground": GREEN, "motif": "banner"},
    "generic": {"sky": SKY, "ground": TEAL, "motif": "globe"},
    "court": {"sky": SKY, "ground": SAND, "motif": "columns"},
    "ship": {"sky": SKY, "ground": TEAL, "motif": "freighter"},
    "cricket": {"sky": SKY, "ground": GREEN, "motif": "bat"},
    "education": {"sky": SKY, "ground": SAND, "motif": "book"},
    "election": {"sky": SKY, "ground": PALE2, "motif": "ballot"},
    "fire": {"sky": NIGHT, "ground": NIGHT, "motif": "flame"},
    "health": {"sky": WHITE, "ground": PALE, "motif": "cross"},
    "market": {"sky": SKY, "ground": SAND, "motif": "stall"},
    "protest": {"sky": SKY, "ground": PALE2, "motif": "placards"},
    "radar": {"sky": NIGHT, "ground": NIGHT, "motif": "sweep"},
    "space": {"sky": NIGHT, "ground": NIGHT, "motif": "rocket"},
    "summit": {"sky": SKY, "ground": SAND, "motif": "peaks"},
    "tech": {"sky": NIGHT, "ground": NIGHT, "motif": "chip"},
    "trophy": {"sky": SKY, "ground": SAND, "motif": "cup"},
    "football": {"sky": SKY, "ground": GREEN, "motif": "ball"},
}


def _fx(x, w, f):
    return x + f * w


def _fy(y, h, f):
    return y + f * h


def _rbox(r, x, y, w, h, fx0, fy0, fx1, fy1, color):
    r.box(_fx(x, w, fx0), _fy(y, h, fy0),
          (fx1 - fx0) * w, (fy1 - fy0) * h, color)


def _rdisc(r, x, y, w, h, fx, fy, fr, color):
    r.disc(_fx(x, w, fx), _fy(y, h, fy), fr * min(w, h), color)


def _rseg(r, x, y, w, h, fx0, fy0, fx1, fy1, fw, color):
    r.seg(_fx(x, w, fx0), _fy(y, h, fy0), _fx(x, w, fx1), _fy(y, h, fy1),
          fw * min(w, h), color)


def _rpoly(r, x, y, w, h, fracs, color):
    r.poly([(_fx(x, w, fx), _fy(y, h, fy)) for fx, fy in fracs], color)


def _stars(r, x, y, w, h, n=8):
    # Fixed pseudo-random starfield (seeded by position, deterministic).
    for i in range(n):
        fx = ((i * 37 + 11) % 97) / 100.0
        fy = ((i * 53 + 7) % 61) / 100.0
        _rdisc(r, x, y, w, h, fx, fy, 0.012, WHITE)


def _scene_tanker(r, x, y, w, h):
    r.box(x, y, w, h, SKY)
    _rdisc(r, x, y, w, h, 0.82, 0.22, 0.09, GOLD)
    r.box(x, _fy(y, h, 0.68), w, h * 0.32, TEAL)
    _rseg(r, x, y, w, h, 0.05, 0.72, 0.95, 0.72, 0.03, WHITE)
    _rbox(r, x, y, w, h, 0.12, 0.42, 0.88, 0.68, (150, 40, 30))
    _rbox(r, x, y, w, h, 0.16, 0.30, 0.34, 0.42, (200, 90, 40))
    _rbox(r, x, y, w, h, 0.38, 0.30, 0.56, 0.42, GOLD)
    _rbox(r, x, y, w, h, 0.60, 0.30, 0.78, 0.42, (90, 130, 60))
    _rdisc(r, x, y, w, h, 0.30, 0.24, 0.05, (200, 200, 200))
    _rdisc(r, x, y, w, h, 0.42, 0.16, 0.04, (220, 220, 220))


def _scene_drone(r, x, y, w, h):
    r.box(x, y, w, h, NIGHT)
    _stars(r, x, y, w, h, 10)
    _rdisc(r, x, y, w, h, 0.85, 0.20, 0.07, (230, 225, 200))
    _rseg(r, x, y, w, h, 0.30, 0.35, 0.70, 0.65, 0.05, (120, 125, 140))
    _rseg(r, x, y, w, h, 0.70, 0.35, 0.30, 0.65, 0.05, (120, 125, 140))
    _rdisc(r, x, y, w, h, 0.50, 0.50, 0.11, (60, 65, 80))
    _rdisc(r, x, y, w, h, 0.50, 0.50, 0.05, RED)
    for fx, fy in ((0.28, 0.33), (0.72, 0.33), (0.28, 0.67), (0.72, 0.67)):
        _rdisc(r, x, y, w, h, fx, fy, 0.06, (160, 165, 180))
    _rdisc(r, x, y, w, h, 0.50, 0.82, 0.05, GOLD)


def _scene_parade(r, x, y, w, h):
    r.box(x, y, w, h, SKY)
    r.box(x, _fy(y, h, 0.72), w, h * 0.28, (90, 90, 100))
    _rseg(r, x, y, w, h, 0.05, 0.72, 0.95, 0.72, 0.02, WHITE)
    _rdisc(r, x, y, w, h, 0.30, 0.38, 0.20, RED)
    _rdisc(r, x, y, w, h, 0.30, 0.42, 0.16, (200, 60, 50))
    _rbox(r, x, y, w, h, 0.26, 0.60, 0.34, 0.70, SAND)
    _rdisc(r, x, y, w, h, 0.68, 0.30, 0.10, GOLD)
    _rdisc(r, x, y, w, h, 0.82, 0.45, 0.07, BLUE)
    for fx, fy in ((0.12, 0.18), (0.55, 0.14), (0.90, 0.20), (0.48, 0.60)):
        _rdisc(r, x, y, w, h, fx, fy, 0.025, (200, 80, 40))


def _scene_city(r, x, y, w, h):
    r.box(x, y, w, h, (28, 40, 80))
    _rdisc(r, x, y, w, h, 0.85, 0.20, 0.08, (230, 225, 200))
    _rbox(r, x, y, w, h, 0.06, 0.45, 0.22, 1.0, NIGHT)
    _rbox(r, x, y, w, h, 0.26, 0.30, 0.44, 1.0, (35, 38, 60))
    _rbox(r, x, y, w, h, 0.48, 0.55, 0.62, 1.0, NIGHT)
    _rbox(r, x, y, w, h, 0.66, 0.35, 0.86, 1.0, (35, 38, 60))
    _rbox(r, x, y, w, h, 0.88, 0.60, 0.98, 1.0, NIGHT)
    for fx, fy in ((0.12, 0.55), (0.32, 0.42), (0.55, 0.65), (0.74, 0.48),
                   (0.36, 0.62), (0.80, 0.55), (0.16, 0.78)):
        _rdisc(r, x, y, w, h, fx, fy, 0.022, GOLD)


def _scene_energy(r, x, y, w, h):
    r.box(x, y, w, h, PALE)
    _rdisc(r, x, y, w, h, 0.82, 0.22, 0.09, GOLD)
    _rbox(r, x, y, w, h, 0.10, 0.55, 0.22, 1.0, (90, 90, 100))
    _rbox(r, x, y, w, h, 0.26, 0.40, 0.36, 1.0, (70, 70, 85))
    _rbox(r, x, y, w, h, 0.40, 0.60, 0.62, 1.0, (90, 90, 100))
    _rbox(r, x, y, w, h, 0.66, 0.45, 0.78, 1.0, (70, 70, 85))
    _rpoly(r, x, y, w, h, [(0.30, 0.40), (0.33, 0.22), (0.36, 0.40)], RED)
    _rdisc(r, x, y, w, h, 0.33, 0.18, 0.05, GOLD)
    _rseg(r, x, y, w, h, 0.10, 0.78, 0.90, 0.78, 0.04, TEAL)


def _scene_chart(r, x, y, w, h):
    r.box(x, y, w, h, PAPER)
    _rseg(r, x, y, w, h, 0.10, 0.85, 0.90, 0.85, 0.03, INK)
    _rseg(r, x, y, w, h, 0.10, 0.85, 0.10, 0.12, 0.03, INK)
    _rbox(r, x, y, w, h, 0.16, 0.55, 0.26, 0.85, BLUE)
    _rbox(r, x, y, w, h, 0.30, 0.42, 0.40, 0.85, GREEN)
    _rbox(r, x, y, w, h, 0.44, 0.62, 0.54, 0.85, RED)
    _rbox(r, x, y, w, h, 0.58, 0.30, 0.68, 0.85, GOLD)
    _rbox(r, x, y, w, h, 0.72, 0.48, 0.82, 0.85, TEAL)
    _rseg(r, x, y, w, h, 0.14, 0.70, 0.32, 0.50, 0.04, NAVY)
    _rseg(r, x, y, w, h, 0.32, 0.50, 0.50, 0.58, 0.04, NAVY)
    _rseg(r, x, y, w, h, 0.50, 0.58, 0.68, 0.30, 0.04, NAVY)
    _rseg(r, x, y, w, h, 0.68, 0.30, 0.86, 0.18, 0.04, NAVY)
    _rdisc(r, x, y, w, h, 0.86, 0.18, 0.05, NAVY)


def _scene_flag(r, x, y, w, h):
    r.box(x, y, w, h, SKY)
    r.box(x, _fy(y, h, 0.78), w, h * 0.22, GREEN)
    _rseg(r, x, y, w, h, 0.18, 0.12, 0.18, 0.85, 0.03, INK)
    _rpoly(r, x, y, w, h, [(0.18, 0.14), (0.78, 0.14), (0.62, 0.30),
                           (0.78, 0.46), (0.18, 0.46)], RED)
    _rdisc(r, x, y, w, h, 0.82, 0.24, 0.08, GOLD)


def _scene_generic(r, x, y, w, h):
    r.box(x, y, w, h, SKY)
    _stars(r, x, y, w, h, 6)
    _rdisc(r, x, y, w, h, 0.50, 0.52, 0.30, TEAL)
    _rdisc(r, x, y, w, h, 0.42, 0.42, 0.08, GREEN)
    _rdisc(r, x, y, w, h, 0.60, 0.60, 0.10, GREEN)
    _rdisc(r, x, y, w, h, 0.58, 0.38, 0.05, SAND)
    _rseg(r, x, y, w, h, 0.20, 0.52, 0.80, 0.52, 0.02, WHITE)


def _scene_court(r, x, y, w, h):
    r.box(x, y, w, h, SKY)
    r.box(x, _fy(y, h, 0.80), w, h * 0.20, SAND)
    _rpoly(r, x, y, w, h, [(0.12, 0.42), (0.50, 0.14), (0.88, 0.42)], PALE2)
    _rbox(r, x, y, w, h, 0.12, 0.42, 0.88, 0.48, INK)
    for fx in (0.20, 0.38, 0.56, 0.74):
        _rbox(r, x, y, w, h, fx, 0.48, fx + 0.07, 0.80, WHITE)
    _rbox(r, x, y, w, h, 0.08, 0.80, 0.92, 0.86, WHITE)


def _scene_ship(r, x, y, w, h):
    r.box(x, y, w, h, SKY)
    _rdisc(r, x, y, w, h, 0.15, 0.20, 0.08, GOLD)
    r.box(x, _fy(y, h, 0.66), w, h * 0.34, TEAL)
    _rpoly(r, x, y, w, h, [(0.10, 0.55), (0.90, 0.55), (0.82, 0.72),
                           (0.18, 0.72)], (40, 45, 70))
    _rbox(r, x, y, w, h, 0.20, 0.38, 0.36, 0.55, RED)
    _rbox(r, x, y, w, h, 0.38, 0.38, 0.54, 0.55, BLUE)
    _rbox(r, x, y, w, h, 0.56, 0.38, 0.72, 0.55, GOLD)
    _rbox(r, x, y, w, h, 0.74, 0.30, 0.82, 0.55, WHITE)
    _rseg(r, x, y, w, h, 0.06, 0.80, 0.94, 0.80, 0.03, WHITE)


def _scene_cricket(r, x, y, w, h):
    r.box(x, y, w, h, SKY)
    r.box(x, _fy(y, h, 0.62), w, h * 0.38, GREEN)
    _rbox(r, x, y, w, h, 0.30, 0.62, 0.70, 0.85, SAND)
    _rseg(r, x, y, w, h, 0.42, 0.20, 0.58, 0.55, 0.05, (150, 110, 60))
    _rdisc(r, x, y, w, h, 0.78, 0.30, 0.05, RED)
    _rbox(r, x, y, w, h, 0.46, 0.72, 0.54, 0.85, WHITE)


def _scene_education(r, x, y, w, h):
    r.box(x, y, w, h, SKY)
    _rpoly(r, x, y, w, h, [(0.15, 0.40), (0.50, 0.28), (0.85, 0.40),
                           (0.85, 0.72), (0.50, 0.60), (0.15, 0.72)], WHITE)
    _rseg(r, x, y, w, h, 0.50, 0.28, 0.50, 0.60, 0.03, INK)
    _rpoly(r, x, y, w, h, [(0.30, 0.18), (0.70, 0.18), (0.50, 0.30)], NIGHT)
    _rseg(r, x, y, w, h, 0.70, 0.18, 0.70, 0.42, 0.03, NIGHT)
    _rdisc(r, x, y, w, h, 0.70, 0.48, 0.04, GOLD)


def _scene_election(r, x, y, w, h):
    r.box(x, y, w, h, SKY)
    r.box(x, _fy(y, h, 0.75), w, h * 0.25, PALE2)
    _rbox(r, x, y, w, h, 0.30, 0.42, 0.70, 0.80, NAVY)
    _rbox(r, x, y, w, h, 0.40, 0.38, 0.60, 0.44, INK)
    _rpoly(r, x, y, w, h, [(0.44, 0.38), (0.56, 0.38), (0.52, 0.20),
                           (0.40, 0.20)], WHITE)
    _rseg(r, x, y, w, h, 0.44, 0.30, 0.52, 0.24, 0.03, RED)


def _scene_fire(r, x, y, w, h):
    r.box(x, y, w, h, NIGHT)
    _rdisc(r, x, y, w, h, 0.50, 0.62, 0.26, (200, 60, 30))
    _rdisc(r, x, y, w, h, 0.50, 0.68, 0.18, GOLD)
    _rpoly(r, x, y, w, h, [(0.50, 0.18), (0.62, 0.45), (0.58, 0.66),
                           (0.42, 0.66), (0.38, 0.45)], (240, 180, 60))
    _rdisc(r, x, y, w, h, 0.50, 0.72, 0.06, WHITE)


def _scene_health(r, x, y, w, h):
    r.box(x, y, w, h, WHITE)
    _rbox(r, x, y, w, h, 0.42, 0.18, 0.58, 0.82, RED)
    _rbox(r, x, y, w, h, 0.20, 0.40, 0.80, 0.60, RED)
    _rseg(r, x, y, w, h, 0.08, 0.88, 0.92, 0.88, 0.02, TEAL)


def _scene_market(r, x, y, w, h):
    r.box(x, y, w, h, SKY)
    _rpoly(r, x, y, w, h, [(0.10, 0.30), (0.90, 0.30), (0.80, 0.50),
                           (0.20, 0.50)], RED)
    _rbox(r, x, y, w, h, 0.10, 0.30, 0.28, 0.50, WHITE)
    _rbox(r, x, y, w, h, 0.46, 0.30, 0.64, 0.50, WHITE)
    _rbox(r, x, y, w, h, 0.82, 0.30, 0.90, 0.50, WHITE)
    _rbox(r, x, y, w, h, 0.18, 0.50, 0.82, 0.85, (120, 80, 40))
    for fx, col in ((0.28, RED), (0.42, GOLD), (0.56, GREEN), (0.70, RED)):
        _rdisc(r, x, y, w, h, fx, 0.62, 0.05, col)


def _scene_protest(r, x, y, w, h):
    r.box(x, y, w, h, SKY)
    r.box(x, _fy(y, h, 0.78), w, h * 0.22, PALE2)
    for fx, col in ((0.18, RED), (0.42, BLUE), (0.66, GOLD), (0.86, GREEN)):
        _rseg(r, x, y, w, h, fx, 0.30, fx, 0.78, 0.03, INK)
        _rbox(r, x, y, w, h, fx - 0.09, 0.14, fx + 0.09, 0.32, col)
    _rdisc(r, x, y, w, h, 0.50, 0.60, 0.06, INK)


def _scene_radar(r, x, y, w, h):
    r.box(x, y, w, h, NIGHT)
    cx, cy = 0.50, 0.52
    for fr in (0.12, 0.22, 0.32):
        pts = []
        for k in range(25):
            a = 2 * math.pi * k / 24.0
            pts.append((_fx(x, w, cx + fr * math.cos(a) * 1.4),
                        _fy(y, h, cy + fr * math.sin(a))))
        for p0, p1 in zip(pts, pts[1:] + pts[:1]):
            r.seg(p0[0], p0[1], p1[0], p1[1], 0.015 * min(w, h), GREEN)
    _rseg(r, x, y, w, h, cx, cy, 0.82, 0.30, 0.03, GREEN)
    _rdisc(r, x, y, w, h, cx, cy, 0.04, GREEN)
    _rdisc(r, x, y, w, h, 0.68, 0.38, 0.04, RED)


def _scene_space(r, x, y, w, h):
    r.box(x, y, w, h, NIGHT)
    _stars(r, x, y, w, h, 12)
    _rpoly(r, x, y, w, h, [(0.46, 0.20), (0.54, 0.20), (0.58, 0.55),
                           (0.42, 0.55)], WHITE)
    _rpoly(r, x, y, w, h, [(0.46, 0.20), (0.54, 0.20), (0.50, 0.08)], RED)
    _rpoly(r, x, y, w, h, [(0.42, 0.55), (0.50, 0.72), (0.58, 0.55)], GOLD)
    _rdisc(r, x, y, w, h, 0.50, 0.42, 0.04, TEAL)


def _scene_summit(r, x, y, w, h):
    r.box(x, y, w, h, SKY)
    _rdisc(r, x, y, w, h, 0.82, 0.20, 0.09, GOLD)
    _rpoly(r, x, y, w, h, [(0.02, 0.95), (0.30, 0.30), (0.58, 0.95)], (90, 110, 130))
    _rpoly(r, x, y, w, h, [(0.40, 0.95), (0.68, 0.18), (0.96, 0.95)], (70, 90, 110))
    _rpoly(r, x, y, w, h, [(0.68, 0.18), (0.62, 0.32), (0.74, 0.32)], WHITE)
    _rseg(r, x, y, w, h, 0.68, 0.18, 0.68, 0.06, 0.02, INK)
    _rpoly(r, x, y, w, h, [(0.68, 0.06), (0.80, 0.10), (0.68, 0.14)], RED)


def _scene_tech(r, x, y, w, h):
    r.box(x, y, w, h, NIGHT)
    _rbox(r, x, y, w, h, 0.32, 0.25, 0.68, 0.75, (40, 50, 80))
    _rbox(r, x, y, w, h, 0.40, 0.35, 0.60, 0.65, TEAL)
    for fy in (0.32, 0.50, 0.68):
        _rseg(r, x, y, w, h, 0.16, fy, 0.32, fy, 0.03, GOLD)
        _rseg(r, x, y, w, h, 0.68, fy, 0.84, fy, 0.03, GOLD)
    for fx in (0.40, 0.50, 0.60):
        _rseg(r, x, y, w, h, fx, 0.10, fx, 0.25, 0.03, GOLD)
        _rseg(r, x, y, w, h, fx, 0.75, fx, 0.90, 0.03, GOLD)


def _scene_trophy(r, x, y, w, h):
    r.box(x, y, w, h, SKY)
    _rpoly(r, x, y, w, h, [(0.30, 0.15), (0.70, 0.15), (0.64, 0.45),
                           (0.36, 0.45)], GOLD)
    _rseg(r, x, y, w, h, 0.30, 0.20, 0.16, 0.32, 0.04, GOLD)
    _rseg(r, x, y, w, h, 0.70, 0.20, 0.84, 0.32, 0.04, GOLD)
    _rbox(r, x, y, w, h, 0.46, 0.45, 0.54, 0.62, GOLD)
    _rbox(r, x, y, w, h, 0.34, 0.62, 0.66, 0.72, (150, 110, 40))
    _rdisc(r, x, y, w, h, 0.50, 0.30, 0.06, WHITE)


def _scene_football(r, x, y, w, h):
    r.box(x, y, w, h, SKY)
    r.box(x, _fy(y, h, 0.60), w, h * 0.40, GREEN)
    _rseg(r, x, y, w, h, 0.05, 0.60, 0.95, 0.60, 0.02, WHITE)
    _rdisc(r, x, y, w, h, 0.50, 0.42, 0.20, WHITE)
    _rdisc(r, x, y, w, h, 0.50, 0.42, 0.07, INK)
    for fx, fy in ((0.34, 0.30), (0.66, 0.30), (0.34, 0.54), (0.66, 0.54)):
        _rdisc(r, x, y, w, h, fx, fy, 0.035, INK)


_SCENE_PAINT = {
    "tanker": _scene_tanker,
    "drone": _scene_drone,
    "parade": _scene_parade,
    "city": _scene_city,
    "energy": _scene_energy,
    "chart": _scene_chart,
    "flag": _scene_flag,
    "generic": _scene_generic,
    "court": _scene_court,
    "ship": _scene_ship,
    "cricket": _scene_cricket,
    "education": _scene_education,
    "election": _scene_election,
    "fire": _scene_fire,
    "health": _scene_health,
    "market": _scene_market,
    "protest": _scene_protest,
    "radar": _scene_radar,
    "space": _scene_space,
    "summit": _scene_summit,
    "tech": _scene_tech,
    "trophy": _scene_trophy,
    "football": _scene_football,
}


def paint_scene(raster, kind, x, y, w, h):
    """Paint one flat illustrated scene into the rectangle (x, y, w, h)."""
    painter = _SCENE_PAINT.get(kind, _scene_generic)
    painter(raster, x, y, w, h)
