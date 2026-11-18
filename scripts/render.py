#!/usr/bin/env python3
"""纸片拼贴 · 逐帧渲染引擎

海报（AI 出图）→ Pillow 逐帧动效 → 程序化 BGM/音效混音 → ffmpeg 编码
零视频 API：所有动态和声音都是代码生成的，改参即可重出片。

用法: python render.py <project_dir> [--size 1080x1920]
"""
import json
import math
import os
import random
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env

FPS = 30
INK = (28, 24, 20)
CREAM = (243, 236, 219)
PAPER_ACCENTS = [(232, 184, 58), (58, 128, 128), (200, 60, 45), (28, 24, 20)]

TITLE_T = 0.20      # 标题拍入（拍内相对时刻，配音前的空档）
WHOOSH_T = 0.46     # 第一件装饰飞入
RIP_T = 0.92        # 第二件纸片

FFMPEG = None
FB = None
FR = None


# ---------------------------------------------------------------- 工具
def ease(kind, p):
    p = max(0.0, min(1.0, p))
    if kind == "out":
        return 1 - (1 - p) ** 2
    if kind == "smooth":
        return p * p * (3 - 2 * p)
    if kind == "back":
        s = 1.9
        q = p - 1
        return 1 + (s + 1) * q ** 3 + s * q ** 2
    return p


def lerp(a, b, q):
    return a + (b - a) * q


def cover(im, w, h):
    s = max(w / im.width, h / im.height)
    im = im.resize((max(w, int(im.width * s + 1)), max(h, int(im.height * s + 1))),
                   Image.LANCZOS)
    x = (im.width - w) // 2
    y = (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def torn_poly(w, h, seed, jag=4):
    r = random.Random(seed)
    pts, step = [], 14
    for x in range(0, w + 1, step):
        pts.append((x, r.randint(0, jag)))
    for y in range(0, h + 1, step):
        pts.append((w - r.randint(0, jag), y))
    for x in range(w, -1, -step):
        pts.append((x, h - r.randint(0, jag)))
    for y in range(h, -1, -step):
        pts.append((r.randint(0, jag), y))
    return pts


def paper(w, h, color, seed, jag=4):
    im = Image.new("RGBA", (w + 8, h + 8), (0, 0, 0, 0))
    ImageDraw.Draw(im).polygon(torn_poly(w, h, seed, jag), fill=color)
    return im.crop((4, 4, 4 + w, 4 + h))


def shadow(im, blur=12, off=(8, 12), alpha=110):
    pad = blur * 2
    canvas = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sh.paste((0, 0, 0, alpha), (pad + off[0], pad + off[1]), im.split()[3])
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)), (0, 0))
    canvas.alpha_composite(im, (pad, pad))
    return canvas, pad


def halftone_disc(r, color):
    S = r * 2 + 8
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([4, 4, S - 4, S - 4], fill=color)
    step = max(6, r // 5)
    for y in range(0, S, step):
        for x in range(0, S, step):
            if (x - S / 2) ** 2 + (y - S / 2) ** 2 < (r * 0.92) ** 2:
                d.ellipse([x, y, x + step * 0.42, y + step * 0.42],
                          fill=(255, 255, 255, 90))
    return im


def washi(w, h, color, angle):
    im = paper(w, h, color, seed=11, jag=2).rotate(angle, expand=True, resample=Image.BICUBIC)
    im.putalpha(im.split()[3].point(lambda v: int(v * 0.85)))
    return im


def _font(path, size):
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ---------------------------------------------------------------- 标题纸条
def title_strip(text, base_fs, accent, seed, maxw):
    """本地渲染的毛边纸条 —— 这正是绝不让 AI 写字的理由：一个字都不会错。"""
    fs = base_fs
    while fs > base_fs * 0.52:
        f = _font(FB, fs)
        track = int(fs * 0.06)
        widths = [f.getbbox(c)[2] - f.getbbox(c)[0] if c != " " else fs * 0.30 for c in text]
        tw = sum(widths) + track * (len(text) - 1)
        if tw + fs * 1.24 <= maxw:
            break
        fs -= 4
    f = _font(FB, fs)
    track = int(fs * 0.06)
    widths = [f.getbbox(c)[2] - f.getbbox(c)[0] if c != " " else fs * 0.30 for c in text]
    tw = int(sum(widths) + track * (len(text) - 1))
    padx, pady = int(fs * 0.62), int(fs * 0.40)
    bw, bh = tw + padx * 2, fs + pady * 2

    base = paper(bw, bh, CREAM, seed)
    under = paper(bw - 30, int(bh * 0.34), accent, seed + 1, jag=3)
    strip = Image.new("RGBA", (bw, bh + 26), (0, 0, 0, 0))
    strip.alpha_composite(under, (18, bh - int(bh * 0.20)))
    strip.alpha_composite(base, (0, 0))

    d = ImageDraw.Draw(strip)
    x = padx
    for c, cw in zip(text, widths):
        d.text((x + track / 2, pady - fs * 0.06), c, font=f, fill=INK)
        x += cw + track
    return strip


# ---------------------------------------------------------------- 装饰件
def decor_set(beat_id, accent, L):
    """两件装饰：胶带 + 半调圆片。奇数拍从左进，偶数拍从右进，都避开底部字幕区。"""
    S = L.S
    if beat_id % 2 == 1:
        return [
            dict(img=washi(int(210 * S), int(54 * S), (232, 214, 172), 18),
                 x=L.W * 0.178, y=L.H * 0.121,
                 sx=-L.W * 0.26, sy=L.H * 0.0625, rot=-14, t0=WHOOSH_T),
            dict(img=halftone_disc(int(96 * S), accent),
                 x=L.W * 0.859, y=L.H * 0.565,
                 sx=L.W * 1.28, sy=L.H * 0.604, rot=0, t0=RIP_T),
        ]
    return [
        dict(img=washi(int(196 * S), int(52 * S), (232, 214, 172), 24),
             x=L.W * 0.828, y=L.H * 0.118,
             sx=L.W * 1.26, sy=L.H * 0.057, rot=12, t0=WHOOSH_T),
        dict(img=halftone_disc(int(100 * S), accent),
             x=L.W * 0.137, y=L.H * 0.609,
             sx=-L.W * 0.28, sy=L.H * 0.651, rot=0, t0=RIP_T),
    ]


# ---------------------------------------------------------------- 字幕
def wrap(text, font, maxw):
    PUNCT = "。，、！？；：）」』】”’"
    lines, cur = [], ""
    for ch in text:
        if font.getlength(cur + ch) > maxw and cur:
            if ch in PUNCT:          # 避头点：标点跟着上一行走，不孤零零掉下去
                cur += ch
                lines.append(cur)
                cur = ""
            else:
                lines.append(cur)
                cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def fit_sub(text, L):
    best_f, best_lines = None, None
    for fs in range(L.sub_fs_hi, L.sub_fs_lo - 1, -1):
        f = _font(FR, fs)
        lines = wrap(text, f, L.sub_maxw)
        best_f, best_lines = f, lines
        if len(lines) <= 2:
            return f, lines
    return best_f, best_lines


def make_subtitle(lines, font):
    lh = int(font.size * 1.55)
    bw = int(max(font.getlength(l) for l in lines)) + 76
    bh = lh * len(lines) + 44
    im = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=14, fill=(18, 16, 14, 175))
    for i, l in enumerate(lines):
        d.text(((bw - font.getlength(l)) / 2, 20 + i * lh), l, font=font, fill=CREAM)
    return im


# ---------------------------------------------------------------- 单拍渲染
def render_beat(beat, poster_path, out_path, accent, L, wm_text, crop_bottom):
    W, H = L.W, L.H
    dur = float(beat["dur"])
    n = max(1, int(round(dur * FPS)))

    src = Image.open(poster_path).convert("RGB")
    if crop_bottom > 0:                      # 去掉 AI 出图右下角的角标
        src = src.crop((0, 0, src.width, max(1, src.height - crop_bottom)))
    base = cover(src, W, H)

    title = None
    if beat.get("title_cn"):
        title = title_strip(beat["title_cn"], L.title_fs, accent,
                            beat["id"] * 3, L.title_maxw)
        title, _ = shadow(title, blur=14, off=(10, 16), alpha=120)

    decors = []
    for it in decor_set(beat["id"], accent, L):
        sh, pad = shadow(it["img"], blur=10, off=(6, 10), alpha=100)
        decors.append(dict(img=sh, pad=pad, **{k: v for k, v in it.items() if k != "img"}))

    sub_f, sub_lines = fit_sub(beat["narration"], L)
    sub_im = make_subtitle(sub_lines, sub_f)
    wm_f = _font(FR, L.wm_fs)

    p = subprocess.Popen(
        [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", out_path],
        stdin=subprocess.PIPE)
    dt = 1.0 / FPS

    for i in range(n):
        t = i * dt
        z = 1.0 + 0.055 * (t / dur)                       # 镜头缓推
        fw, fh = int(W * z), int(H * z)
        frame = base.resize((fw, fh), Image.BILINEAR)
        ox = (fw - W) // 2
        oy = max(0, min(fh - H, (fh - H) // 2 + int(10 * (t / dur))))
        frame = frame.crop((ox, oy, ox + W, oy + H)).convert("RGBA")

        for d_ in decors:
            if t < d_["t0"]:
                continue
            q = ease("back", (t - d_["t0"]) / 0.55)
            x = lerp(d_["sx"], d_["x"], q)
            y = lerp(d_["sy"], d_["y"], q)
            sway = 3.0 * math.sin(t * 1.7 + d_["t0"] * 5)
            im = d_["img"]
            if d_["rot"]:
                im = im.rotate(d_["rot"] * (1 - q), resample=Image.BICUBIC)
            frame.alpha_composite(im, (int(x - d_["pad"]), int(y - d_["pad"] + sway)))

        shake = (0, 0)
        if title is not None and t >= TITLE_T:
            q = ease("back", (t - TITLE_T) / 0.34)
            s = lerp(1.34, 1.0, q)
            tim = title.resize((int(title.width * s), int(title.height * s)), Image.BILINEAR)
            tim = tim.rotate(lerp(-6.0, -1.4, q), resample=Image.BICUBIC, expand=True)
            cx = W // 2 + int(10 * (1 - q) * math.sin(t * 40))
            cy = L.title_y + int(6 * (1 - q))
            if q < 0.99:
                amp = 16 * math.exp(-9 * max(0.0, t - TITLE_T))
                shake = (amp * math.sin((t - TITLE_T) * 70),
                         amp * math.cos((t - TITLE_T) * 60))
            frame.alpha_composite(tim, (int(cx - tim.width / 2), int(cy - tim.height / 2)))

        if shake != (0, 0):
            frame = frame.transform(frame.size, Image.AFFINE,
                                    (1, 0, -shake[0], 0, 1, -shake[1]),
                                    resample=Image.BILINEAR)

        sa = ease("out", (t - 0.42) / 0.35)
        if sa > 0:
            sim = sub_im.copy()
            if sa < 1:
                sim.putalpha(sim.split()[3].point(lambda v: int(v * sa)))
            frame.alpha_composite(sim, ((W - sub_im.width) // 2, L.sub_y))

        if wm_text:
            d = ImageDraw.Draw(frame)
            tw = d.textlength(wm_text, font=wm_f)
            for dx, dy in ((2, 3), (1, 1)):
                d.text((W - tw - L.wm_margin + dx, L.wm_margin - 44 + dy),
                       wm_text, font=wm_f, fill=(0, 0, 0, 90))
            d.text((W - tw - L.wm_margin, L.wm_margin - 44), wm_text, font=wm_f,
                   fill=(255, 255, 255, 205))

        if beat["id"] > 1 and i < 4:                       # 转场白闪，遮住硬切
            a = (238, 152, 72, 26)[i]
            frame = Image.alpha_composite(
                frame, Image.new("RGBA", (W, H), (255, 252, 244, a)))

        p.stdin.write(frame.convert("RGB").tobytes())

    p.stdin.close()
    p.wait()
    print(f"[beat {beat['id']}] {n}f {dur}s -> {os.path.basename(out_path)}", flush=True)


# ---------------------------------------------------------------- 主流程
def main():
    args = [a for a in sys.argv[1:]]
    size = None
    if "--size" in args:
        i = args.index("--size")
        size = args[i + 1]
        del args[i:i + 2]
    proj, bpath, doc = _env.load_project(args[0] if args else ".")

    global FFMPEG, FB, FR
    FFMPEG = _env.ffmpeg()
    FB, FR = _env.font_bold(), _env.font_regular()

    if size:
        w, h = size.lower().split("x")
        L = _env.Layout(width=int(w), height=int(h))
    else:
        L = _env.Layout(doc.get("aspect", "9:16"))

    build = os.path.join(proj, "build")
    os.makedirs(build, exist_ok=True)
    posters = doc.get("posters", {})
    crop_ratio = doc.get("poster_crop_bottom_ratio", 0.04)
    wm = doc.get("watermark") or ""

    starts, sfx, segs = {}, [], []
    t0 = 0.0
    for k, b in enumerate(doc["beats"]):
        accent = PAPER_ACCENTS[k % len(PAPER_ACCENTS)]
        starts[str(b["id"])] = round(t0, 3)
        poster_rel = b.get("poster") or posters.get(str(b["id"]))
        if not poster_rel:
            raise SystemExit(f"第 {b['id']} 拍没有配海报（posters.{b['id']}）。")
        poster_path = _env.resolve(proj, poster_rel)
        if not os.path.isfile(poster_path):
            raise SystemExit(f"海报不存在：{poster_path}")

        src_h = Image.open(poster_path).height
        seg = os.path.join(build, f"beat_{b['id']}.mp4")
        render_beat(b, poster_path, seg, accent, L, wm,
                    int(round(src_h * crop_ratio)))
        segs.append(seg)

        # 音效卡在动作上：标题拍入 / 第一件飞入 / 第二件贴入 / 转场前 riser
        sfx.append({"type": "slap", "t": round(t0 + TITLE_T, 3), "gain": 0.80})
        sfx.append({"type": "whoosh", "t": round(t0 + WHOOSH_T, 3), "gain": 0.45})
        sfx.append({"type": "tape", "t": round(t0 + RIP_T, 3), "gain": 0.30})
        if b["id"] > 1:
            sfx.append({"type": "riser", "t": round(max(0.0, t0 - 0.34), 3), "gain": 0.30})
        t0 += float(b["dur"])

    total = round(sum(float(b["dur"]) for b in doc["beats"]), 3)
    sfx.append({"type": "bell", "t": round(max(0.0, t0 - 0.80), 3), "gain": 0.34})
    events = {"total_dur": total, "beats": starts, "sfx": sfx, "size": [L.W, L.H]}
    json.dump(events, open(os.path.join(build, "events.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    lst = os.path.join(build, "v.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for s in segs:
            f.write("file '%s'\n" % s.replace("\\", "/"))
    silent = os.path.join(build, "video.mp4")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", lst, "-c", "copy", silent], check=True)

    import audio as audio_mod
    wav = audio_mod.build_mix(proj, doc, events)

    final = os.path.join(proj, doc.get("output", "final.mp4"))
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", silent, "-i", wav,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", "-shortest", final], check=True)

    mb = os.path.getsize(final) / 1024 / 1024
    print(f"FINAL: {final}  {total}s  {L.W}x{L.H}  {mb:.1f}MB", flush=True)


if __name__ == "__main__":
    main()
