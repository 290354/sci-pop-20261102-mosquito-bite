# 科普爆点动画周刊 · 第 2 期：蚊子的「手术」

> **为什么你几乎感觉不到它在扎你**
> 它没有刀，没有针。只有一根比头发丝还细的管子，和两排软软的齿。
> 可它每次都能进去，而且你几乎察觉不到——直到几小时后那个包鼓起来。

- **成片**：[`video/episode.mp4`](video/episode.mp4)（1280×720 / 30 fps / **4 分 45 秒** / 立体声：解说 + 配乐）
- **字幕**：[`video/episode.srt`](video/episode.srt)（随片交付，画面内也烧录了字幕）
- **封面**：[`cover.png`](cover.png)（1280×720）
- **脚本**：[`script.md`](script.md) · **选题**：[`选题.md`](选题.md)
- **源码**：`src/engine.py`（逐帧绘制引擎）、`src/render.py`（多进程渲染）、`src/tts.py`（配音分段与对齐）、`src/bgm.py`（合成配乐与混音）、`src/mksubs.py`（SRT/画面字幕）、`src/cover.py`

## 成片规格

| 项 | 值 |
|---|---|
| 分辨率 | 1280×720（横屏 16:9） |
| 帧率 | 30 fps |
| 时长 | 284.8 秒（4:44.8，落在 4:30–5:30 窗口内） |
| 音轨 | AAC 立体声：中文解说（edge-tts `zh-CN-YunxiNeural`，语速 −4%，带 90 Hz 高通与 3:1 压缩）+ 程序合成氛围配乐（低通 4.2 kHz，混音 −10 dB 左右，章节切换处留白） |
| 总帧数 | 8549 帧 |

## 制作路线：B —— 逐帧渲染（HTML/Canvas 同构思路，落地为 PIL）

**为什么不是 A（Manim）**：本期是生物机制 + 尺度对比类题材，核心是"两排齿来回锯动""皮肤分层里口器推进""神经波形被压平"这类连续量绘制；CJK 字幕密集，用 Pillow + Noto CJK 可控且无 LaTeX / TeX Live / Cairo 依赖。同时本机 ffmpeg 不带 `libx264`，只能用 `libopenh264`，渲染必须走"先出帧、后编码"的路线——这与逐帧渲染天然契合。

**实现要点**

- 渲染是**确定性**的：`engine.render(t)` 只依赖秒数 `t`，任意 `t` 都能独立出一帧，因此可以多进程乱序渲染。
- 视觉规范：背景 `#0E1116`、正文 `#ECE6D9`，主色仅 `#58C4DD` / `#F4D345` / `#FC6255` 三色；中文字体 Noto Serif/Sans CJK SC；所有文字先 `measureText`（`textbbox`）再绘制，超宽自动缩字号，字幕最多两行、宽 980 px，保证不出画。
- 节奏：每 8–15 秒必有视觉变化（齿列逐根生成、热区扩散、血包膨胀、波形衰减、波纹外扩），无整屏文字一次性淡入、无 PPT 式翻页。
- 风格参考：`code-animation-prompts` 的 M1（白板手绘"先看见、再命名"）与 B3（粒子聚形，用于呼吸气流）；分镜节奏参考 `fy-code-animation` 的 modules/recipes。只借鉴提示词与组织方式，未引入其依赖。

## 配音档位：L1（edge-tts）

三个音色各合成约 11 秒试听（`audio/audition_*.mp3`：Yunxi 11.02 s / Yunyang 11.09 s / Xiaoxiao 11.35 s），选定 **`zh-CN-YunxiNeural`**：句尾不塌、数字读得清，接近科普播报。共 6 组、46 句，段间插入 0.55 s 静音，组间 0.5–1.2 s。

## 如何复现

```bash
# 0) 依赖
pip install pillow numpy edge-tts
apt-get install -y fonts-noto-cjk          # Noto Serif/Sans CJK SC
ffmpeg -version                            # 本机需含 libopenh264 或 libx264

# 1) 解说分段（含试听样本）
python src/tts.py                          # -> audio/part_XX.mp3, src/timeline.json
python src/mksubs.py                       # -> src/subs.json, video/episode.srt
python src/bgm.py                          # -> audio/voice.wav, audio/bgm.wav（入库前转 mp3）

# 2) 逐帧渲染（5 进程，约 2 分钟）
python src/render.py frames                # -> frames/f000000.jpg ...

# 3) 编码与混音
ffmpeg -y -framerate 30 -i frames/f%06d.jpg -c:v libopenh264 -b:v 3000k \
       -pix_fmt yuv420p -r 30 -an video/_v.mp4
ffmpeg -y -i video/_v.mp4 -i audio/voice.mp3 -i audio/bgm.mp3 -filter_complex \
  "[1:a]highpass=f=90,acompressor=threshold=-18dB:ratio=3:attack=5:release=120[v];[2:a]volume=0.30,lowpass=f=4200[b];[v][b]amix=inputs=2:duration=first:dropout_transition=0,alimiter=limit=0.95,aformat=sample_fmts=fltp:channel_layouts=stereo[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 160k -shortest video/episode.mp4

# 4) 封面
python src/cover.py                        # -> cover.png
```

## 选题来源

| 用途 | 链接 |
|---|---|
| 热度环境：B 站 2026-11-01 全站综合热门（知识/科普区入口） | https://www.bilibili.com/video/BV15vxc6bEZz |
| 当日热门第一（自然科普，播放 627 万，用于说明题材热度） | https://www.bilibili.com/video/BV14txF65Efd |
| 备选选题：冰立方抓中微子与 2026 诺奖解读 | https://www.toutiao.com/article/7702546125181485568 |
| 备选选题：光遗传学让失明者复明 | https://www.toutiao.com/article/7703205013820047922 |
| 备选选题：把地球冷冻能否缓解温室效应 | https://www.hunantoday.cn/news/xhn/202611/34142683.html |
| 备选选题：摇粒绒"70 万根微塑料" | https://www.toutiao.com/article/7702977026096988710/ |
| 备选选题：少吃 30% 与 DNA 突变 | https://cloud.kepuchina.cn/newSearch/imgText?id=7515914558351212544 |
| 备选选题：人与狗同床睡 | https://www.163.com/dy/article/LANAAP8L0526DQM7.html |

## 返修记录（2026-11-06）

1. **时长补到 4:44.8**（原 3:28）。新增 9 句解说：口器的六根零件与下唇刀鞘、锯动时持续吐唾沫、体重翻倍、别抓与冷敷。重配音、重写字幕、重渲染 8549 帧。
2. **修掉音画错位 25 秒。** 原 `tts.py` 的 `SEQ` 分段比脚本整体前移：`mech` 段（7–11 句）实际装的是「拎不出来 / 越拉越紧」，而画面上已经是皮肤剖面；`evid` 段（12–18 句）在讲「皮肤屏障 / 温差」，画面却是放大镜里的齿列。现已按每个场景的画法重新划分 6 组（0-4 / 5-10 / 11-20 / 21-30 / 31-36 / 37-45）。
3. **场景节拍不再写死秒数。** 每个场景加了一个「设计时长」常量，场景变长时按 `DESIGN/dur` 缩放局部时间；齿列生成、血包膨胀另行改成按场景时长比例推进，补长后不会出现「动画演完干等 40 秒」。
4. **配乐和弦原写死 0/19/42/63… 秒**，改由 `timeline.json` 的章节起点推导，改文案不用再回来对秒数。

## 已知瑕疵

1. **画面是符号化的示意，不是解剖学插图。** 两排齿、皮肤四层、血管位置均为示意比例，不代表真实尺寸；数字（2–5 微升、两到三分钟、0.3 ℃）取自通行的科普口径，量级正确但不作精确引用。
2. **配乐为程序合成**（正弦叠加 + 噪声低通 + 心跳脉冲），可听但织体简单；章节切换处有 1.2 s 留白，个别转场会显得突然。
3. 解说为单音色直读，未做逐句语速微调。

## 目录

```
README.md  cover.png  选题.md  script.md
audio/    解说分段、试听样本、voice.mp3、bgm.mp3、timeline
src/      engine.py render.py tts.py bgm.py mksubs.py cover.py segs.json timeline.json subs.json
video/    episode.mp4  episode.srt
qa/       抽帧质检图
```
