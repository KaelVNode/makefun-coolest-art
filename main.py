#!/usr/bin/env python3
"""Sky Whale — a colossal blue whale swims through a dusk sky above a neon
city, rising toward a huge pale moon. Pure Python 3 stdlib, deterministic:
the same bytes every run. Writes entry.png to $MAKEFUN_OUTPUT_DIR (/output).

Style: bold flat illustration with soft gradients — one huge central shape
(the whale) so the piece reads at 300px, a dusk palette (indigo, magenta,
gold), and a clean vector look. No text, no network, no randomness outside
a fixed seed.
"""
import math
import os
import random
import struct
import zlib

W, H = 1024, 1024
OUT = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
RNG = random.Random(20261113)

# ---------------------------------------------------------------- canvas
# img is a flat RGB bytearray; px(i) addresses pixel i = y*W + x.
img = bytearray(W * H * 3)


def put(x, y, r, g, b):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        img[i] = r
        img[i + 1] = g
        img[i + 2] = b


def blend(x, y, r, g, b, a):
    """Blend colour (r,g,b) over pixel (x,y) with coverage a in [0,1]."""
    if a <= 0.0 or not (0 <= x < W and 0 <= y < H):
        return
    if a >= 1.0:
        put(x, y, r, g, b)
        return
    i = (y * W + x) * 3
    ia = 1.0 - a
    img[i] = int(img[i] * ia + r * a)
    img[i + 1] = int(img[i + 1] * ia + g * a)
    img[i + 2] = int(img[i + 2] * ia + b * a)


def lerp(c1, c2, t):
    return (int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t))


def smoothstep(a, b, x):
    t = (x - a) / (b - a)
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * (3.0 - 2.0 * t)


# ------------------------------------------------------------ primitives
def disc(cx, cy, rad, col, glow=0.0, glow_col=None):
    """Filled disc with a soft edge; optional radial glow halo."""
    x0 = int(cx - rad - glow)
    x1 = int(cx + rad + glow)
    y0 = int(cy - rad - glow)
    y1 = int(cy + rad + glow)
    for y in range(max(0, y0), min(H, y1 + 1)):
        dy = y - cy
        for x in range(max(0, x0), min(W, x1 + 1)):
            dx = x - cx
            d = math.sqrt(dx * dx + dy * dy)
            if glow > 0.0 and d > rad:
                if glow_col is not None:
                    a = max(0.0, 1.0 - (d - rad) / glow) ** 2 * 0.55
                    blend(x, y, glow_col[0], glow_col[1], glow_col[2], a)
            elif d <= rad + 1.2:
                a = 1.0 - smoothstep(rad - 1.2, rad + 1.2, d)
                blend(x, y, col[0], col[1], col[2], a)


def ellipse(cx, cy, rx, ry, rot, col, edge=1.5):
    """Filled rotated ellipse with a soft edge. rot in radians."""
    co, si = math.cos(rot), math.sin(rot)
    x0 = int(cx - rx - ry - 2)
    x1 = int(cx + rx + ry + 2)
    y0 = int(cy - rx - ry - 2)
    y1 = int(cy + rx + ry + 2)
    for y in range(max(0, y0), min(H, y1 + 1)):
        for x in range(max(0, x0), min(W, x1 + 1)):
            dx, dy = x - cx, y - cy
            lx = dx * co + dy * si
            ly = -dx * si + dy * co
            q = (lx * lx) / (rx * rx) + (ly * ly) / (ry * ry)
            if q < 1.06:
                a = 1.0 - smoothstep(0.94, 1.06, q)
                blend(x, y, col[0], col[1], col[2], a)


def ring_arc(cx, cy, rx, ry, rot, width, col, a_min, a_max):
    """Thin arc of a rotated ellipse: angles a_min..a_max (radians, in the
    ellipse's local frame, 0 = +x axis). Used for rim light and grooves."""
    co, si = math.cos(rot), math.sin(rot)
    x0 = int(cx - rx - ry - 2)
    x1 = int(cx + rx + ry + 2)
    y0 = int(cy - rx - ry - 2)
    y1 = int(cy + rx + ry + 2)
    for y in range(max(0, y0), min(H, y1 + 1)):
        for x in range(max(0, x0), min(W, x1 + 1)):
            dx, dy = x - cx, y - cy
            lx = dx * co + dy * si
            ly = -dx * si + dy * co
            q = math.sqrt((lx * lx) / (rx * rx) + (ly * ly) / (ry * ry))
            ang = math.atan2(ly / ry, lx / rx)
            if abs(q - 1.0) < width / max(rx, ry) and a_min <= ang <= a_max:
                a = 1.0 - abs(q - 1.0) / (width / max(rx, ry))
                blend(x, y, col[0], col[1], col[2], max(0.0, a) * 0.9)


def rect(x0, y0, x1, y1, col):
    for y in range(max(0, y0), min(H, y1)):
        base = (y * W + max(0, x0)) * 3
        for x in range(max(0, x0), min(W, x1)):
            img[base] = col[0]
            img[base + 1] = col[1]
            img[base + 2] = col[2]
            base += 3


# ------------------------------------------------------------------- sky
# Dusk gradient, top to bottom (indigo -> violet -> magenta -> ember gold).
SKY = [(0.00, (16, 8, 43)), (0.30, (44, 20, 80)), (0.55, (87, 32, 107)),
       (0.75, (158, 52, 96)), (0.90, (222, 96, 62)), (1.00, (247, 158, 60))]


def sky_color(t):
    for i in range(len(SKY) - 1):
        t0, c0 = SKY[i]
        t1, c1 = SKY[i + 1]
        if t0 <= t <= t1:
            return lerp(c0, c1, (t - t0) / (t1 - t0))
    return SKY[-1][1]


for _y in range(H):
    _c = sky_color(_y / (H - 1))
    _base = _y * W * 3
    for _x in range(W):
        img[_base] = _c[0]
        img[_base + 1] = _c[1]
        img[_base + 2] = _c[2]
        _base += 3

# Stars: seeded, denser and brighter higher up, none below the city haze.
for _ in range(320):
    _sx = RNG.randrange(0, W)
    _sy = int(RNG.random() ** 1.6 * 700)
    _br = 0.35 + 0.65 * RNG.random()
    _s = 1 if RNG.random() < 0.8 else 2
    for _dy in range(-_s, _s + 1):
        for _dx in range(-_s, _s + 1):
            _a = _br * max(0.0, 1.0 - (abs(_dx) + abs(_dy)) / (_s + 1.0))
            blend(_sx + _dx, _sy + _dy, 255, 244, 220, _a * 0.85)

# The moon: huge pale disc, upper right, with a warm halo and soft craters.
disc(848, 168, 74, (255, 243, 214), glow=150.0, glow_col=(255, 214, 150))
disc(830, 152, 12, (238, 222, 186))
disc(868, 188, 8, (238, 222, 186))
disc(852, 196, 5, (240, 226, 192))
disc(822, 186, 6, (240, 226, 192))

# ------------------------------------------------------------------ city
# Dark skyline along the bottom: near-black indigo slabs, warm lit windows,
# a few antennae. The whale swims above it, so the city is a quiet base.
CITY_TOP = 836
rect(0, CITY_TOP, W, H, (11, 8, 23))
# Warm haze just above the rooftops.
for _y in range(CITY_TOP - 46, CITY_TOP):
    _t = (_y - (CITY_TOP - 46)) / 46.0
    _c = lerp((247, 158, 60), (158, 52, 96), _t)
    for _x in range(W):
        blend(_x, _y, _c[0], _c[1], _c[2], 0.20 * (1.0 - _t))

_x = -12
while _x < W + 12:
    _bw = RNG.randrange(46, 118)
    _bh = RNG.randrange(52, 196)
    _bx0, _by0 = _x, CITY_TOP - _bh
    rect(_bx0, _by0, _bx0 + _bw, CITY_TOP + 4, (13, 10, 28))
    # Rooftop details: water tank or antenna on some slabs.
    if RNG.random() < 0.35:
        rect(_bx0 + _bw // 2 - 2, _by0 - 16, _bx0 + _bw // 2 + 2, _by0, (13, 10, 28))
        put(_bx0 + _bw // 2, _by0 - 18, 255, 70, 70)
    elif RNG.random() < 0.3:
        rect(_bx0 + 8, _by0 - 10, _bx0 + 26, _by0, (13, 10, 28))
    # Lit windows: warm, sparse, seeded.
    for _wy in range(_by0 + 12, CITY_TOP - 8, 17):
        for _wx in range(_bx0 + 8, _bx0 + _bw - 8, 14):
            if RNG.random() < 0.42:
                _wc = (255, 210, 122) if RNG.random() < 0.75 else (255, 158, 94)
                rect(_wx, _wy, _wx + 6, _wy + 8, _wc)
    _x += _bw + RNG.randrange(2, 14)

# ----------------------------------------------------------------- whale
# The hero: a colossal whale rising diagonally toward the moon, nose up.
# Body: one big rotated ellipse; belly: a lighter ellipse below the axis;
# tail and fins: smaller rotated ellipses; rim light: a cyan arc on top.
WX, WY, WR = 470.0, 480.0, math.radians(-13)
ellipse(WX, WY, 308, 136, WR, (27, 58, 84))
ellipse(WX + 18, WY + 44, 276, 94, WR, (46, 96, 128))
# Belly grooves: three pale arcs following the body's curve.
for _k, _rr in enumerate((232, 204, 176)):
    ring_arc(WX + 18, WY + 44, _rr, 76 - _k * 8, WR, 3.0,
             (126, 190, 214), math.radians(8), math.radians(172))
# Tail: a short stock plus two flukes spreading from the rear tip.
ellipse(196, 545, 62, 28, WR, (27, 58, 84))
ellipse(138, 492, 76, 24, math.radians(32), (27, 58, 84))
ellipse(146, 598, 76, 24, math.radians(-34), (27, 58, 84))
# Pectoral fin, tucked under the body.
ellipse(430, 566, 74, 22, math.radians(24), (22, 48, 70))
# Dorsal fin on the back.
ellipse(400, 372, 52, 16, math.radians(-30), (22, 48, 70))
# Cyan rim light along the top of the body, catching the moon.
ring_arc(WX, WY, 308, 136, WR, 4.0, (127, 227, 255),
         math.radians(-168), math.radians(-18))
# Eye: white ring, dark pupil, tiny highlight — placed on the head (right).
_disc = disc
_disc(738, 424, 12, (235, 245, 250))
_disc(740, 425, 6, (10, 14, 24))
_disc(736, 421, 2, (255, 255, 255))
# Mouth: a gentle dark arc under the eye.
ring_arc(712, 452, 96, 34, math.radians(-13), 3.0, (14, 30, 48),
         math.radians(18), math.radians(96))

# Spout: a fan of glowing droplets bursting from the blowhole toward the
# moon, sizes shrinking as they rise, plus a few four-point sparkles.
_bx, _by = 668, 372
for _i in range(46):
    _a = math.radians(-118 + RNG.random() * 62)
    _d = 26 + RNG.random() ** 1.4 * 190
    _px = _bx + math.cos(_a) * _d
    _py = _by + math.sin(_a) * _d * 0.82 - _d * 0.16
    _r = max(1.2, 5.5 - _d / 42.0)
    disc(_px, _py, _r, (190, 240, 255), glow=_r * 2.2,
         glow_col=(140, 220, 255))
for _sx, _sy, _sr in ((600, 210, 9), (724, 268, 7), (560, 300, 6), (790, 210, 8)):
    for _dx, _dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        blend(int(_sx + _dx * _sr), int(_sy + _dy * _sr),
              255, 250, 230, 0.95 if (_dx, _dy) == (0, 0) else 0.55)
    blend(int(_sx), int(_sy), 255, 250, 230, 1.0)

# A few tiny birds, dark chevrons high in the sky, for scale and life.
for _bx2, _by2, _bs in ((300, 250, 9), (352, 216, 7), (262, 300, 6), (920, 330, 8)):
    for _t in range(_bs + 1):
        put(int(_bx2 - _t), int(_by2 + _t // 2), 24, 16, 40)
        put(int(_bx2 + _t), int(_by2 + _t // 2), 24, 16, 40)

# ------------------------------------------------------- vignette + save
def save_png(path):
    """Write img as a PNG (filter 0 rows, zlib). Vignette is folded in
    during the row pass so the encode stays a single sweep."""
    raw = bytearray()
    cx, cy = W / 2.0, H / 2.0
    for y in range(H):
        raw.append(0)
        dy = (y - cy) / (H * 0.72)
        for x in range(W):
            dx = (x - cx) / (W * 0.72)
            v = 1.0 - 0.16 * max(0.0, dx * dx + dy * dy - 0.55)
            i = (y * W + x) * 3
            raw.append(int(img[i] * v))
            raw.append(int(img[i + 1] * v))
            raw.append(int(img[i + 2] * v))
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    os.makedirs(OUT, exist_ok=True)
    n = save_png(os.path.join(OUT, "entry.png"))
    print(f"wrote entry.png ({n} bytes)")


if __name__ == "__main__":
    main()
