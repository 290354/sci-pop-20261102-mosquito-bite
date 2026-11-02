from PIL import Image, ImageDraw
import engine as E
img = E.render(196)
img = img.filter(E.ImageFilter.GaussianBlur(3))
img = Image.blend(img, Image.new("RGB", (E.W, E.H), E.BG), 0.62)
d = ImageDraw.Draw(img); d._image = img
d.rectangle([0, 0, E.W, E.H], fill=None)
E.text_c(d, 640, 120, "科普爆点动画周刊", E.F("sansb", 24), E.YEL, 1.0)
E.text_c(d, 640, 166, "第 02 期", E.F("sans", 20), E.INK, 0.55)
E.text_c(d, 640, 220, "蚊子的「手术」", E.F("serifb", 92), E.INK, 1.0)
d.line([(500, 348), (780, 348)], fill=E.YEL, width=3)
E.text_c(d, 640, 372, "它扎你的时候，为什么你几乎感觉不到", E.F("sans", 32), E.INK, 0.9)
E.text_c(d, 640, 430, "两排齿 · 四十次锯动 · 一个被调慢的警报", E.F("sans", 26), E.BLUE, 0.9)
img.save("cover.png")
