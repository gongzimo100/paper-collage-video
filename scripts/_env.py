#!/usr/bin/env python3
"""公共环境解析：ffmpeg 路径、中文字体、画幅布局。

三个脚本（tts / render / audio）共用，避免各处硬编码。
任何一项找不到，都给出能直接照抄的修复命令，而不是抛个裸的 FileNotFoundError。
"""
import os
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)


# ---------------------------------------------------------------- ffmpeg
def _ffmpeg_candidates():
    yield os.environ.get("FFMPEG_BIN")
    for name in ("ffmpeg.exe", "ffmpeg"):
        yield os.path.join(SKILL_ROOT, "tools", name)
    yield shutil.which("ffmpeg")
    # 项目自带工具目录（老项目沿用 ./tools/ffmpeg.exe 的习惯）
    yield os.path.join(os.getcwd(), "tools", "ffmpeg.exe")
    try:
        import imageio_ffmpeg  # 最省事的兜底：pip 装完就有静态二进制
        yield imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass


def ffmpeg():
    for c in _ffmpeg_candidates():
        if c and os.path.isfile(c):
            return c
    raise SystemExit(
        "找不到 ffmpeg。任选一种修：\n"
        "  1) pip install imageio-ffmpeg      （推荐，装完自动被识别）\n"
        "  2) python scripts/doctor.py --install\n"
        "  3) 把 ffmpeg.exe 放进 skill 目录的 tools/ 下，或设环境变量 FFMPEG_BIN"
    )


def probe_duration(path):
    """用 ffmpeg -i 解析时长（不依赖 ffprobe，很多静态包不带）。"""
    import re
    r = subprocess.run([ffmpeg(), "-hide_banner", "-i", path],
                       capture_output=True, text=True, errors="ignore")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr or "")
    if not m:
        return 0.0
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def probe_info(path):
    """返回 (宽, 高, 时长)。给自检用。"""
    import re
    r = subprocess.run([ffmpeg(), "-hide_banner", "-i", path],
                       capture_output=True, text=True, errors="ignore")
    txt = r.stderr or ""
    dur = 0.0
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", txt)
    if m:
        h, mi, s = m.groups()
        dur = int(h) * 3600 + int(mi) * 60 + float(s)
    w = h_ = 0
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", txt)
    if m:
        w, h_ = int(m.group(1)), int(m.group(2))
    return w, h_, round(dur, 3)


# ---------------------------------------------------------------- 字体
_BOLD = [
    "C:/Windows/Fonts/msyhbd.ttc",        # 微软雅黑 Bold，Windows 首选
    "C:/Windows/Fonts/msyhbd.ttf",
    "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf",
]
_REG = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyh.ttf",
    "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
]


def _pick(cands, env_key):
    v = os.environ.get(env_key)
    if v and os.path.isfile(v):
        return v
    for p in cands:
        if os.path.isfile(p):
            return p
    # 全都没有：退回 PIL 内置位图字体（能跑，但中文会是方块，会在 stdout 里警告）
    return ""


def font_bold():
    p = _pick(_BOLD, "COLLAGE_FONT_BOLD")
    if not p:
        print("[warn] 没找到中文粗体，标题可能显示为方块。"
              "设 COLLAGE_FONT_BOLD=/path/to/font.ttc 指定字体。", flush=True)
    return p


def font_regular():
    p = _pick(_REG, "COLLAGE_FONT_REG") or font_bold()
    return p


# ---------------------------------------------------------------- 画幅
ASPECTS = {"9:16": (1080, 1920), "16:9": (1920, 1080),
           "1:1": (1080, 1080), "4:5": (1080, 1350)}


class Layout:
    """所有像素常量都按画幅推导，横竖屏共用一套代码。

    - 字号跟短边走（1080 短边为基准），换画幅不变视觉重量
    - 纵向位置跟高走（比例不变），横屏也不会有字幕掉到画面外
    """

    def __init__(self, aspect="9:16", width=None, height=None):
        if width and height:
            self.W, self.H = int(width), int(height)
        else:
            self.W, self.H = ASPECTS.get(aspect, ASPECTS["9:16"])
        self.S = min(self.W, self.H) / 1080.0        # 像素缩放基准
        land = self.W > self.H                       # 横屏字幕要放大一点才看得清
        k = 1.25 if land else 1.0
        self.title_fs = int(118 * self.S)
        self.title_y = int(self.H * 0.156)
        self.sub_y = int(self.H * 0.8125)
        self.sub_fs_hi = max(22, int(42 * self.S * k))
        self.sub_fs_lo = max(16, int(30 * self.S * k))
        self.sub_maxw = int(self.W * (0.66 if land else 0.852))
        self.title_maxw = int(self.W * 0.88)
        self.wm_fs = max(16, int(26 * self.S))
        self.wm_margin = int(44 * self.S)
        self.shadow_pad = int(12 * self.S)

    def rel(self, fx, fy):
        return int(self.W * fx), int(self.H * fy)


# ---------------------------------------------------------------- 项目
def load_project(proj):
    """读 beats.json，顺手做一遍基础校验。"""
    import json
    proj = os.path.abspath(proj)
    bpath = os.path.join(proj, "beats.json")
    if not os.path.isfile(bpath):
        raise SystemExit(f"没有找到 {bpath} —— 先按 references/beats-spec.md 写一份分镜。")
    doc = json.load(open(bpath, encoding="utf-8"))
    if not doc.get("beats"):
        raise SystemExit("beats.json 里 beats 是空的。")
    for i, b in enumerate(doc["beats"], 1):
        b.setdefault("id", i)
        if not b.get("narration"):
            raise SystemExit(f"第 {b['id']} 拍没有 narration。")
    return proj, bpath, doc


def resolve(proj, p):
    if not p:
        return p
    return p if os.path.isabs(p) else os.path.join(proj, p)
