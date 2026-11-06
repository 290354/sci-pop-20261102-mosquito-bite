import asyncio, edge_tts, json, subprocess, os

segs = json.load(open("src/segs.json"))
VOICE = "zh-CN-YunxiNeural"
GAP = 0.55  # 默认段间留白（秒）

SEQ = [
    ("cold", 0, 4, 0.8),
    ("tension", 5, 10, 0.6),
    ("mech", 11, 20, 0.6),
    ("evid", 21, 30, 0.5),
    ("infer", 31, 36, 0.5),
    ("close", 37, 45, 1.2),
]

async def synth(text, out):
    if os.path.exists(out) and os.path.getsize(out) > 1000:
        return
    for _ in range(3):
        try:
            await edge_tts.Communicate(text, VOICE, rate="-4%").save(out)
            return
        except Exception as e:
            print("retry", out, e)
            await asyncio.sleep(1.2)

async def build_seg(_k, kind, start, end, hold):
    ci = _k; si = start
    parts = []
    for i in range(start, end + 1):
        p = f"audio/seg_{i:02d}.mp3"
        await synth(segs[i]["text"], p)
        parts.append(p)
    lst = f"audio/_list_{ci:02d}.txt"
    with open(lst, "w") as f:
        for i, p in enumerate(parts):
            f.write(f"file '{os.path.abspath(p)}'\n")
            if i != len(parts) - 1:
                f.write(f"file '{os.path.abspath(f'audio/_gap_{GAP}.mp3')}'\n")
    out = f"audio/part_{ci:02d}.mp3"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out], check=True)
    return ci, si, end, hold

async def main():
    # 生成静音间隔（44.1k 单声道 mp3）
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"anullsrc=r=24000:cl=mono", "-t", str(GAP), "-q:a", "9", f"audio/_gap_{GAP}.mp3"], check=True)
    res = await asyncio.gather(*[build_seg(k, *v) for k, v in enumerate(SEQ) if v[2] < len(segs)])
    meta = []
    t = 0.0
    for entry in sorted(res, key=lambda x: x[0]):
        ci = entry[0]
        d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                           "-of", "csv=p=0", f"audio/part_{ci:02d}.mp3"]))
        meta.append({"idx": ci, "kind": SEQ[ci][0], "r0": SEQ[ci][1], "r1": SEQ[ci][2],
                     "start": round(t, 3), "dur": round(d, 3), "hold": entry[3]})
        t += d + entry[3]
    meta.append({"idx": len(meta), "kind": "end", "start": round(t, 3), "dur": 0.0, "hold": 0.0})
    json.dump(meta, open("src/timeline.json", "w"), ensure_ascii=False, indent=1)
    print([(m["idx"], m["kind"], m["start"], round(m["start"] + m["dur"], 1)) for m in meta[:-1]])
    print("TOTAL", round(t, 2))

asyncio.run(main())
