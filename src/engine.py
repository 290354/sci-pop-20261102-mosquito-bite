# -*- coding: utf-8 -*-
"""逐帧渲染引擎：蚊子的「手术」（第 2 期）
纯 PIL 绘制，确定性 renderAt(t) 语义（t 秒 -> 一张 1280x720 帧）。
风格：深底 #0E1116 / 正文 #ECE6D9 / 三主色 #58C4DD #F4D345 #FC6255（3b1b 配色）
"""
import json, math, os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1280, 720
BG = (14, 17, 22)
INK = (236, 230, 217)
DIM = (108, 114, 124)
BLUE = (88, 196, 221)
YEL = (244, 211, 69)
RED = (252, 98, 85)
FR = 30

SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"
SERIFB = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
SANSB = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

_fc = {}
def F(kind, size):
    key = (kind, int(size))
    if key in _fc:
        return _fc[key]
    path = {"serif": SERIF, "serifb": SERIFB, "sans": SANS, "sansb": SANSB}[kind]
    f = ImageFont.truetype(path, int(size), index=2 if "CJK" in path and path.endswith(".ttc") else 0)
    _fc[key] = f
    return f

def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)

def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))

def lerp(a, b, u):
    return a + (b - a) * u

def blend(c1, c2, u):
    return tuple(int(lerp(c1[i], c2[i], clamp(u))) for i in range(3))

def seg(t, t0, t1, feather=0.35):
    """在 [t0,t1] 内的存在度 0..1，两端羽化"""
    if t < t0 - feather or t > t1 + feather:
        return 0.0
    return min(clamp((t - t0) / feather), clamp((t1 - t) / feather), 1.0)

# ---------------- 文本 ----------------
def measure(d, s, f):
    b = d.textbbox((0, 0), s, font=f)
    return b[2] - b[0], b[3] - b[1]

def fit_font(d, s, kind, size, maxw):
    while size > 16:
        w, _ = measure(d, s, F(kind, size))
        if w <= maxw:
            return F(kind, size)
        size -= 2
    return F(kind, size)

def text_c(d, cx, y, s, f, fill, alpha=1.0, anchor_center=True, glow=None):
    if alpha <= 0.01:
        return
    w, h = measure(d, s, f)
    x = cx - w / 2 if anchor_center else cx
    col = fill if alpha >= 0.99 else blend(BG, fill, alpha)
    if glow:
        d.text((x, y), s, font=f, fill=blend(BG, glow, alpha * 0.35))
        d.text((x - 1, y), s, font=f, fill=col)
    d.text((x, y), s, font=f, fill=col)

def wrap(d, s, f, maxw):
    lines, cur = [], ""
    for ch in s:
        if ch == "\n":
            lines.append(cur); cur = ""; continue
        if measure(d, cur + ch, f)[0] > maxw and cur:
            lines.append(cur); cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines

def subtitle(d, s, alpha=1.0):
    if alpha <= 0.01 or not s:
        return
    f = F("sans", 27)
    lines = wrap(d, s, f, 980)[:2]
    lh = 40
    box_h = lh * len(lines) + 14
    y0 = H - 26 - box_h
    d.rounded_rectangle([120, y0, W - 120, y0 + box_h], 8, fill=blend(d._image.getpixel((5, 5)), (0, 0, 0), 0.55 * alpha))
    for i, ln in enumerate(lines):
        text_c(d, W / 2, y0 + 7 + i * lh, ln, f, INK, alpha)

def headline(d, s, alpha=1.0, y=70, color=INK, size=46):
    if alpha <= 0.01:
        return
    f = fit_font(d, s, "serifb", size, 1120)
    text_c(d, W / 2, y, s, f, color, alpha)

def chip(d, x, y, s, color, alpha=1.0, fsize=22):
    if alpha <= 0.01:
        return
    f = F("sansb", fsize)
    w, h = measure(d, s, f)
    d.rounded_rectangle([x, y, x + w + 26, y + h + 16], 18, outline=blend(BG, color, alpha), width=2)
    text_c(d, x + 13, y + 6, s, f, color, alpha, anchor_center=False)

# ---------------- 背景 ----------------
def draw_bg(d, t):
    d.rectangle([0, 0, W, H], fill=BG)
    # 极淡网格 + 缓慢漂移，制造纵深
    for i in range(0, W, 64):
        x = i + (t * 6) % 64
        d.line([(x, 0), (x, H)], fill=(22, 26, 33), width=1)
    for j in range(0, H, 64):
        d.line([(0, j), (W, j)], fill=(22, 26, 33), width=1)

def vignette(img):
    if not hasattr(vignette, "_c"):
        m = Image.new("L", (W, H), 0)
        md = ImageDraw.Draw(m)
        md.ellipse([-W * 0.25, -H * 0.35, W * 1.25, H * 1.35], fill=255)
        m = m.filter(ImageFilter.GaussianBlur(120))
        vignette._c = m
    black = Image.new("RGB", (W, H), BG)
    return Image.composite(img, black, vignette._c)

# ---------------- 图案元素 ----------------
def dust(d, t, n=70, seed=7, alpha=1.0):
    for i in range(n):
        rnd = (i * 9301 + seed * 49297) % 233280 / 233280
        rnd2 = (i * 4999 + seed * 7919) % 104729 / 104729
        x = (rnd * W + t * (6 + rnd2 * 14)) % W
        y = (rnd2 * H + math.sin(t * 0.3 + i) * 12) % H
        a = 0.12 + 0.5 * rnd
        d.ellipse([x, y, x + 1.8, y + 1.8], fill=blend(BG, INK, a * alpha))

def co2_stream(d, t, ox, oy, u, alpha=1.0, spread=1.0, n=26, color=BLUE):
    if alpha <= 0.01:
        return
    for i in range(n):
        p = ((t * 0.32 + i / n) % 1.0)
        x = ox + p * 470 * spread
        y = oy + math.sin(p * 7 + i * 1.3 + t * 0.6) * (22 + 34 * p) * spread
        r = 2 + 5 * p
        c = blend(BG, color, (1 - p) * 0.9 * alpha * u)
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)

def mosquito_side(d, cx, cy, s=1.0, alpha=1.0, phase=0.0, color=(60, 64, 70), dirn=1):
    if alpha <= 0.01:
        return
    body = blend(BG, color, alpha)
    wing = blend(BG, (150, 175, 190), alpha * 0.55)
    ax = cx + dirn * 95 * s; ay = cy - 8 * s
    d.ellipse([ax - 13 * s, ay - 13 * s, ax + 13 * s, ay + 13 * s], fill=body)
    d.ellipse([cx - 46 * s, cy - 4 * s, cx + 46 * s, cy + 26 * s], fill=body)
    for k in range(3):
        lx = cx - 20 * s + k * 22 * s
        d.line([(lx, cy + 22 * s), (lx - 8 * s, cy + (70 + 10 * math.sin(phase + k)) * s)], fill=body, width=max(1, int(2 * s)))
    d.line([(cx - dirn * 40 * s, cy + 10 * s), (cx - dirn * 118 * s, cy - 6 * s)], fill=body, width=max(1, int(3 * s)))
    wob = math.sin(phase) * 10 * s
    d.line([(cx - dirn * 118 * s, cy - 6 * s), (cx - dirn * 330 * s, cy - 34 * s + wob)],
           fill=blend(BG, RED, alpha * 0.95), width=max(1, int(3.5 * s)))
    for k in (-1, 1):
        d.ellipse([cx - 18 * s, cy - (26 + 4 * math.sin(phase * 1.7)) * s - (10 if k < 0 else 0) * s,
                   cx + 26 * s, cy + 6 * s], outline=wing, width=max(1, int(2 * s)))

def magnifier(d, cx, cy, r, t, alpha=1.0):
    if alpha <= 0.01:
        return
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=blend(BG, BLUE, alpha * 0.9), width=3)
    d.ellipse([cx - r + 10, cy - r + 10, cx + r - 10, cy + r - 10], outline=blend(BG, BLUE, alpha * 0.3), width=1)
    d.line([(cx + r * 0.7, cy + r * 0.7), (cx + r * 1.5, cy + r * 1.5)], fill=blend(BG, BLUE, alpha * 0.8), width=8)

def number_pop(d, cx, cy, s, f, alpha=1.0, color=YEL, sub=None):
    if alpha <= 0.01:
        return
    text_c(d, cx, cy, s, f, color, alpha)
    if sub:
        text_c(d, cx, cy + 86, sub, F("sans", 24), INK, alpha * 0.8)

# ---------------- 场景 ----------------
def scene_cold(d, t, tl, dur):
    u = clamp(t / dur)
    text_c(d, 640, 128, "它扎你的时候，你几乎感觉不到", F("serifb", 30), INK, 1.0)
    d.ellipse([-160, 250, 520, 930], fill=(17, 20, 26))
    dust(d, t, 60, 3)
    # 房间暗箱
    d.rounded_rectangle([60, 60, W - 60, H - 120], 26, outline=(38, 43, 52), width=2)
    # 人（简化剪影）+ 脚踝
    cx = 470
    d.ellipse([cx - 52, 172, cx + 52, 276], fill=(30, 34, 41))
    d.rounded_rectangle([cx - 96, 268, cx + 96, 520], 46, fill=(30, 34, 41))
    d.rounded_rectangle([cx - 120, 500, cx + 160, 580], 40, fill=(30, 34, 41))
    d.ellipse([cx + 150, 520, cx + 236, 580], fill=(48, 53, 62))
    # 呼吸 -> CO2
    co2_stream(d, t, cx + 30, 250, 1.0, alpha=seg(t, tl[0], tl[0] + 24), spread=1.0)
    # 蚊子
    x0, y0 = 1120, 210
    x1, y1 = cx + 214, 536
    p = ease(clamp((t - tl[0] - 4) / 11.0))
    mx, my = lerp(x0, x1, p), lerp(y0, y1, p) + math.sin(t * 3) * 8 * (1 - p)
    if t > tl[0] + 3:
        mosquito_side(d, mx, my - 40, s=0.62 + 0.12 * math.sin(t * 1.3) * (1 - p), alpha=seg(t, tl[0] + 3, tl[0] + 30), phase=t * 9)
    # 落脚后：放大提示 + 一条缝
    a2 = seg(t, tl[0] + 9, tl[0] + 26)
    if a2 > 0.01:
        rx, ry = cx + 236, 550
        d.ellipse([rx - 44, ry - 44, rx + 44, ry + 44], outline=blend(BG, YEL, a2 * 0.9), width=3)
        d.line([(rx + 40, ry + 30), (rx + 300, ry + 150)], fill=blend(BG, YEL, a2 * 0.8), width=2)
        chip(d, rx + 300, ry + 138, "一条缝：0.02 毫米", YEL, a2)

def scene_tension(d, t, tl, dur):
    a = seg(t, tl[0], tl[1] + 1)
    magnifier(d, W / 2, 300, 150, t, a * 0.9)
    # 针状口器（放大）与两排齿
    cx, cy = W / 2, 300
    d.line([(cx - 300, cy - 6), (cx + 300, cy - 6)], fill=blend(BG, INK, a * 0.7), width=3)
    for k in range(9):
        xx = cx - 190 + k * 44
        d.line([(xx, cy - 20), (xx + 12, cy + 26)], fill=blend(BG, RED, a * 0.9), width=4)
        d.line([(xx + 14, cy + 8), (xx + 26, cy - 38)], fill=blend(BG, YEL, a * 0.75), width=4)
    if a > 0.2:
        chip(d, cx - 150, cy + 150, "红：上唇齿列", RED, a * 0.9, 20)
        chip(d, cx + 20, cy + 150, "黄：下唇齿列（错开）", YEL, a * 0.9, 20)
    # 毛刺长度对比
    b = seg(t, tl[0] + 6, tl[1] + 1)
    if b > 0.01:
        d.line([(150, 560), (420, 560)], fill=blend(BG, BLUE, b), width=5)
        text_c(d, 285, 572, "蚊子口器 约 2 毫米", F("sans", 22), BLUE, b)
        d.line([(700, 560), (720, 560)], fill=blend(BG, RED, b), width=5)
        text_c(d, 780, 572, "一根头发 约 0.07 毫米", F("sans", 22), RED, b)
    c = seg(t, tl[0] + 16, tl[1] + 1)
    if c > 0.01:
        text_c(d, W / 2, 150, "按常理：扎不进去", F("serifb", 34), INK, c)
        c2 = seg(t, tl[0] + 21, tl[1] + 1)
        text_c(d, W / 2, 196, "可是它每次都进去了", F("serifb", 34), YEL, c2)

def scene_mech(d, t, tl, dur):
    a = seg(t, tl[0], tl[1] + 1)
    # 皮肤分层
    layers = [("角质层", (46, 52, 62), 150, 40), ("表皮", (74, 54, 56), 190, 70),
              ("真皮 · 毛细血管", (58, 40, 44), 260, 150), ("皮下脂肪", (40, 44, 52), 410, 90)]
    for i, (name, col, y, hh) in enumerate(layers):
        d.rectangle([160, y, 1120, y + hh], fill=blend(BG, col, a))
        d.line([(160, y), (1120, y)], fill=blend(BG, DIM, a * 0.6), width=1)
    for k in range(3):
        pts = []
        for i in range(0, 40):
            x = 200 + i * 23
            yy = 330 + k * 40 + math.sin(i * 0.6 + k + t * 0.8) * 7
            pts.append((x, yy))
        d.line(pts, fill=blend(BG, RED, a * 0.85), width=6)
    # 三处落脚点：脚跟 / 手腕 / 脖颈 —— 路最短
    b = seg(t, tl[0] + 24, tl[1] + 1)
    if b > 0.01:
        for k, (nx, ny, label) in enumerate([(360, 300, "脚跟"), (640, 300, "手腕"), (920, 300, "脖颈")]):
            al = b * clamp((t - tl[0] - 24 - k * 3) / 1.5)
            d.ellipse([nx - 26, ny - 26, nx + 26, ny + 26], outline=blend(BG, YEL, al * 0.9), width=2)
            text_c(d, nx, ny - 52, label, F("sans", 22), YEL, al)
    # 热区 + 口器推进
    c = seg(t, tl[0] + 16, tl[1] + 1)
    p = ease(clamp((t - tl[0] - 16) / 12.0))
    if c > 0.01:
        for rr in range(120, 12, -8):
            d.ellipse([640 - rr, 300 - rr * 0.8, 640 + rr, 300 + rr * 0.8],
                      fill=blend(d._image.getpixel((640 + rr // 2, 300)), (255, 120, 70), c * 0.035))
    ty = lerp(120, 322, p)
    d.line([(640, 96), (640, ty)], fill=blend(BG, INK, a), width=4)
    d.ellipse([632, ty - 6, 648, ty + 6], fill=blend(BG, RED, a))
    text_c(d, 300, 158, "角质层", F("sans", 20), INK, a * 0.6, anchor_center=False)
    text_c(d, 300, 204, "表皮", F("sans", 20), INK, a * 0.6, anchor_center=False)
    text_c(d, 300, 276, "真皮", F("sans", 20), INK, a * 0.6, anchor_center=False)
    if p > 0.7:
        chip(d, 700, ty + 20, "温差：0.3 ℃ 就够", YEL, seg(t, tl[0] + 24, tl[1] + 1))

def scene_evid(d, t, tl, dur):
    a = seg(t, tl[0], tl[1] + 1)
    cx, cy = 420, 330
    magnifier(d, cx, cy, 160, t, a * 0.9)
    # 两排错开的齿
    p = ease(clamp((t - tl[0] - 3) / 8.0))
    n = int(9 * p)
    for k in range(n):
        xx = cx - 130 + k * 32
        yy = cy - 40 + math.sin(k * 0.7) * 4
        d.line([(xx, yy), (xx + 14, yy + 62)], fill=blend(BG, INK, a * 0.9), width=4)
        d.line([(xx + 16, yy - 6), (xx + 30, yy + 52)], fill=blend(BG, RED, a * 0.65), width=4)
    # 锯动
    m = seg(t, tl[0] + 12, tl[0] + 22)
    if m > 0.01:
        off = math.sin(t * 12) * 10
        d.rounded_rectangle([cx - 140 + off, cy + 80, cx + 150 + off, cy + 96], 8, outline=blend(BG, YEL, m), width=2)
        text_c(d, cx + 5, cy + 108, "来回 40 次 = 锯开", F("sans", 20), YEL, m)
    # 右侧：皮肤表面 + 吸血
    sx0, sy0, sx1, sy1 = 700, 150, 1140, 430
    d.rounded_rectangle([sx0, sy0, sx1, sy1], 16, outline=blend(BG, DIM, a * 0.6), width=1)
    d.line([(sx0 + 20, sy0 + 80), (sx1 - 20, sy0 + 80)], fill=blend(BG, (120, 90, 80), a * 0.9), width=10)
    b = ease(clamp((t - tl[0] - 14) / 10.0))
    if b > 0.01:
        rw = 40 + 90 * b; rh = 26 + 54 * b
        d.ellipse([900 - rw, sy0 + 80 - rh, 900 + rw, sy0 + 80 + rh], fill=blend(BG, (150, 46, 44), a * 0.95))
        d.line([(900, sy0 + 10), (900, sy0 + 62)], fill=blend(BG, INK, a), width=4)
    text_c(d, 920, sy0 + 240, "2–5 微升", F("serifb", 44), YEL, seg(t, tl[0] + 20, tl[1] + 1))
    text_c(d, 920, sy0 + 296, "约等于 一滴水的 1/20", F("sans", 20), INK, seg(t, tl[0] + 20, tl[1] + 1) * 0.75)

def scene_infer(d, t, tl, dur):
    a = seg(t, tl[0], tl[1] + 1)
    lt = t - tl[0]
    d.rounded_rectangle([120, 150, 620, 470], 16, outline=blend(BG, DIM, a * 0.5), width=1)
    # 波形：前段（叮）高频；压住痛觉标签亮起后振幅按时间常数衰减
    tags_t = [16, 21, 26]
    atten = 1.0
    for k, tk in enumerate(tags_t):
        if lt > tk and k == 2:
            atten = 0.18 + 0.82 * math.exp(-(lt - tk) / 5.0)
    pts = []
    for i in range(0, 100):
        x = 140 + i * 4.8
        wave = math.sin(i * 0.55 - t * 7) * 40 * atten
        pts.append((x, 310 + wave))
    d.line(pts, fill=blend(BG, BLUE, a * 0.95), width=3)
    text_c(d, 580, 420, "痛觉信号", F("sans", 20), BLUE, a * 0.6, anchor_center=False)
    if atten < 0.5:
        text_c(d, 580, 446, "被压平", F("sans", 20), RED, a * clamp((0.5 - atten) * 3))
    for k, name in enumerate(["血管扩张", "血液不凝固", "压住痛觉"]):
        chip(d, 672, 168 + k * 62, name, [RED, YEL, BLUE][k], seg(lt, tags_t[k], tl[1] + 1))
    text_c(d, 672, 372, "唾沫里的三重任务", F("sans", 22), INK, a * 0.75, anchor_center=False)
    d.line([(672, 404), (836, 404)], fill=blend(BG, DIM, a * 0.6), width=1)
    prog = clamp(lt / (tl[1] - tl[0]))
    d.rectangle([672, 440, 900, 446], fill=blend(BG, (34, 40, 48), a))
    d.rectangle([672, 440, 672 + 228 * prog, 446], fill=blend(BG, YEL, a * 0.8))
    text_c(d, 672, 458, "叮的那一刻 —— 痒的那一刻", F("sans", 18), INK, a * 0.55, anchor_center=False)
    b = seg(lt, 32, tl[1] + 1)
    if b > 0.01:
        d.line([(160, 560), (1120, 560)], fill=blend(BG, DIM, b * 0.7), width=2)
        p = clamp((lt - 32) / 10.0)
        d.line([(160, 560), (160 + 960 * p, 560)], fill=blend(BG, YEL, b), width=6)
        text_c(d, 150, 500, "叮", F("serifb", 34), INK, b * clamp(p * 3), anchor_center=False)
        text_c(d, 1076, 500, "痒", F("serifb", 34), RED, b * clamp((p - 0.75) * 4), anchor_center=False)

def scene_close(d, t, tl, dur):
    u = clamp((t - tl[0]) / max(0.1, tl[1] - tl[0]))
    a = seg(t, tl[0], tl[1] + 1)
    cx = 380
    d.ellipse([cx - 46, 210, cx + 46, 302], fill=(30, 34, 41))
    d.rounded_rectangle([cx - 84, 296, cx + 84, 500], 40, fill=(30, 34, 41))
    d.rounded_rectangle([cx - 104, 486, cx + 150, 554], 34, fill=(30, 34, 41))
    # 肿包 + 免疫波纹（第 1 拍：事后警报）
    b = clamp((u - 0.10) / 0.10)
    if b > 0.01:
        rr = 18 + 40 * b
        d.ellipse([cx + 168 - rr, 526 - rr, cx + 168 + rr, 526 + rr], fill=blend(BG, (160, 52, 50), b * 0.95))
        for k in range(4):
            ring = (t * 0.8 + k * 0.25) % 1.0
            rad = 26 + ring * 96
            d.ellipse([cx + 168 - rad, 526 - rad, cx + 168 + rad, 526 + rad],
                      outline=blend(BG, RED, (1 - ring) * 0.45 * b), width=2)
        text_c(d, cx - 60, 600, "肿包 = 事后的警报", F("sans", 22), RED, b * 0.9)
    # 第 1 拍文案
    p1 = seg(t, tl[0] + 3, tl[0] + 17, 0.8)
    if p1 > 0.01:
        text_c(d, 880, 236, "不出声，", F("serifb", 60), INK, p1)
        text_c(d, 880, 308, "不等于没发生。", F("serifb", 60), INK, p1)
        text_c(d, 880, 410, "它只是把你的警报，调慢了半拍。", F("sans", 26), BLUE, p1 * 0.9)
    # 第 2 拍：收束大结论
    p2 = seg(t, tl[0] + 26, tl[1] + 1, 1.0)
    if p2 > 0.01:
        d.rounded_rectangle([200, 200, 1080, 430], 20, fill=blend(BG, (10, 13, 17), p2 * 0.85),
                            outline=blend(BG, YEL, p2 * 0.5), width=2)
        text_c(d, 640, 240, "一只没有刀的动物，", F("serifb", 52), INK, p2)
        text_c(d, 640, 316, "为什么比刀更让你难受？", F("serifb", 52), YEL, p2)
        text_c(d, 640, 388, "因为它先改写你的感觉，再动手。", F("sans", 26), BLUE, p2 * 0.9)

SCENES = [scene_cold, scene_tension, scene_mech, scene_evid, scene_infer, scene_close]
TITLES = {0: None, 1: "一根没有任何刀刃的口器", 2: "口器怎么找到血", 3: "两把错开的锉刀",
          4: "被调慢的警报", 5: "不出声，不等于没发生"}

# ---------------- 主渲染 ----------------
TL = json.load(open(os.path.join(os.path.dirname(__file__), "timeline.json")))
SEGS = json.load(open(os.path.join(os.path.dirname(__file__), "segs.json")))
SUBS = json.load(open(os.path.join(os.path.dirname(__file__), "subs.json")))
TOTAL = TL[-1]["start"]

def render(t):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d._image = img
    def _dr(s):
        nonlocal d
        return s
    draw_bg(d, t)
    # 当前章节
    cur = 0
    for k, m in enumerate(TL[:-1]):
        if t >= m["start"]:
            cur = k
    m = TL[cur]
    scene = SCENES[cur]
    dur = (TL[cur + 1]["start"] - m["start"])
    scene(d, t - m["start"], (0, m["dur"]), dur)
    # 章节标题
    ttl_end = 5.6 if cur != 5 else 25.0
    if TITLES.get(cur) and 0.6 < (t - m["start"]) < ttl_end:
        al = seg(t - m["start"], 0.6, ttl_end, 0.8)
        f = F("serifb", 40)
        s = f"{['冷开场','张力','第一章 · 机制','第二章 · 证据','第三章 · 边界','收束'][cur]}"
        text_c(d, W / 2, 40, s, F("sans", 20), YEL, al * 0.85)
        text_c(d, W / 2, 70, TITLES[cur], f, INK, al)
        d.line([(W / 2 - 60, 128), (W / 2 + 60, 128)], fill=blend(BG, YEL, al * 0.7), width=2)
    # 收束小节：标题在中心大字出现时淡出，避免与结论文字重复抢位
    if cur == 5 and (t - m["start"]) > 25.0:
        pass
    # 字幕
    img = d._image
    d = ImageDraw.Draw(img)
    d._image = img
    for s in SUBS:
        if s["s"] <= t < s["e"]:
            a = min(clamp((t - s["s"]) / 0.12), clamp((s["e"] - t) / 0.12))
            subtitle(d, s["text"], a)
            break
    img = vignette(d._image)
    d = ImageDraw.Draw(img)
    d._image = img
    # 页眉 / 页脚
    text_c(d, 46, 24, "科普爆点动画周刊 · 第 2 期", F("sans", 17), INK, 0.35, anchor_center=False)
    mm, ss = int(t) // 60, int(t) % 60
    text_c(d, W - 118, 24, f"{mm:01d}:{ss:02d}", F("sans", 17), INK, 0.35, anchor_center=False)
    d.rectangle([0, H - 4, int(W * clamp(t / TOTAL)), H], fill=(70, 86, 104))
    return img

if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    out = sys.argv[3]
    os.makedirs(out, exist_ok=True)
    for i in range(a, b):
        render(i / FR).save(os.path.join(out, "f%06d.jpg" % i), quality=90)
