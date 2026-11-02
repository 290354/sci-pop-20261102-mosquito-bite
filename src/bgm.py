# -*- coding: utf-8 -*-
"""L3 音轨合成：合成器生成氛围配乐（无版权依赖）+ 解说拼接 + 混音"""
import json, subprocess, numpy as np, wave

SR = 44100
tl = json.load(open("src/timeline.json"))
TOTAL = tl[-1]["start"]

# ---------- 1. 解说轨：整段拼接（保持与 SRT 完全一致的时间轴） ----------
lst = "audio/_all_parts.txt"
with open(lst, "w") as f:
    for m in tl[:-1]:
        f.write(f"file '{__import__('os').path.abspath('audio/part_%02d.mp3' % m['idx'])}'\n")
        f.write(f"file '{__import__('os').path.abspath('audio/_gap_%.2f.mp3' % round(m['hold'],1))}'\n")
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
                "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", "audio/voice.wav"], check=True)

# ---------- 2. 合成配乐 ----------
n = int((TOTAL + 1.2) * SR)
t = np.arange(n) / SR
music = np.zeros(n, dtype=np.float64)

def note(f, dur, amp, pan=0.0, harm=(1.0, 0.35, 0.16, 0.07), attack=0.9, release=1.6, drift=0.0):
    m = int(dur * SR)
    tt = np.arange(m) / SR
    env = np.minimum(1, tt / attack) * np.minimum(1, np.maximum(0, (dur - tt) / release))
    vib = np.sin(2 * np.pi * 0.13 * tt + pan * 3) * 1.2  # 轻微音高游移，用人声般的不稳定感
    s = np.zeros(m)
    for k, a in enumerate(harm, 1):
        fk = f * k * (1 + drift * k)
        s += a * np.sin(2 * np.pi * fk * tt + vib * k)
    return s * env * amp

# D 小调五音：D3 F3 G3 A3 C4 D4 F4 A4
FREQ = {"D3": 146.83, "F3": 174.61, "G3": 196.00, "A3": 220.00,
        "C4": 261.63, "D4": 293.66, "F4": 349.23, "A4": 440.00, "E4": 329.63}
CH = [  # (起始, 长度, [音], 基础音量)
    (0.0, 20.0, ["D3", "A3"], 0.30),
    (19.0, 24.0, ["F3", "C4"], 0.30),
    (42.0, 22.0, ["D3", "F3", "A3"], 0.30),
    (63.0, 22.0, ["G3", "D4"], 0.28),
    (84.0, 23.0, ["A3", "E4"], 0.30),
    (106.0, 24.0, ["F3", "C4", "F4"], 0.28),
    (129.0, 22.0, ["D3", "A3", "D4"], 0.32),
    (150.0, 22.0, ["G3", "D4"], 0.28),
    (171.0, 20.0, ["F3", "C4", "A4"], 0.26),
    (190.0, 21.0, ["D3", "A3", "D4"], 0.32),
]
for s0, ln, notes, amp in CH:
    i0 = int(s0 * SR)
    for k, nn in enumerate(notes):
        seg = note(FREQ[nn], ln, amp / (1 + 0.4 * k), pan=k - 1, drift=0.0015)
        m = min(len(seg), n - i0)
        music[i0:i0 + m] += seg[:m]

# 低频脉冲（心跳感）：每 2.2 秒一次，前 40 秒更明显 —— 呼应“黑暗中的搜寻”
for k in range(int(TOTAL / 2.2)):
    tt0 = k * 2.2 + 0.2
    i0 = int(tt0 * SR)
    m = int(0.35 * SR)
    if i0 + m >= n:
        break
    tt = np.arange(m) / SR
    env = np.exp(-tt * 9)
    music[i0:i0 + m] += 0.10 * np.sin(2 * np.pi * 55 * tt) * env

# 空气感：低通噪声 + 缓变
rng = np.random.default_rng(7)
noise = rng.standard_normal(n)
# 简易一阶低通
b = 0.02
lp = np.empty(n)
acc = 0.0
for i in range(0, n, 1):
    acc += b * (noise[i] - acc)
    lp[i] = acc
music += lp * 0.20 * (0.6 + 0.4 * np.sin(2 * np.pi * 0.03 * t))

# 章节切换处做 1.2 秒留白（压低到近乎无声），突出解说
for m in tl[1:-1]:
    s0 = m["start"]
    a, bnd = int((s0 - 0.9) * SR), int((s0 + 0.5) * SR)
    fade = np.ones(bnd - a)
    fade[: int(0.7 * SR)] = np.linspace(1, 0.12, int(0.7 * SR))
    fade[int(0.7 * SR):] = np.linspace(0.12, 1, bnd - a - int(0.7 * SR))
    music[a:bnd] *= fade

# 结尾渐弱
end_fade = int(2.5 * SR)
music[-end_fade:] *= np.linspace(1, 0, end_fade)

music = music / (np.max(np.abs(music)) + 1e-9) * 0.22  # 峰值 -13 dBFS 左右，再整体压 -8dB
music *= 0.40
# 轻微立体声：左右延时
left = music
right = np.roll(music, int(0.011 * SR)) * 0.92
st = np.stack([left, right], axis=1)
st = np.clip(st, -1, 1)
pcm = (st * 32767).astype(np.int16)
with wave.open("audio/bgm.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("bgm", TOTAL)
