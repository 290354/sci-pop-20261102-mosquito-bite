import json, subprocess
segs = json.load(open("src/segs.json"))
tl = json.load(open("src/timeline.json"))
GAP = 0.55
subs = []
for m in tl[:-1]:
    t = m["start"]
    for i in range(m["r0"], m["r1"] + 1):
        d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                           "-of", "csv=p=0", f"audio/seg_{i:02d}.mp3"]))
        subs.append({"s": round(t, 2), "e": round(t + d, 2), "text": segs[i]["text"]})
        t += d + GAP
json.dump(subs, open("src/subs.json", "w"), ensure_ascii=False, indent=1)

def ts(x):
    h = int(x // 3600); m = int(x % 3600 // 60); s = int(x % 60); ms = int(round((x - int(x)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

with open("video/episode.srt", "w") as f:
    for k, x in enumerate(subs, 1):
        f.write(f"{k}\n{ts(x['s'])} --> {ts(x['e'])}\n{x['text']}\n\n")
print(len(subs), subs[-1]["e"])
