#!/usr/bin/env python3
"""BGM + 音效 + 配音混音。全部程序化合成，零外部素材、零 API 成本。

- BGM：欢快尤克里里（拨弦谐波合成）+ 鼓组 + 钢片琴点缀，默认 C-G-Am-F 112 BPM
- 音效：纸片拍入 / 飞入风切 / 胶带撕拉 / 转场 riser / 收尾铃
- 侧链：人声一起来，音乐自动压下去，说完再抬回来

之所以不用素材库：合成出来的节奏天然跟分镜对齐，也不用担心版权。

用法: python audio.py <project_dir>
"""
import json
import os
import subprocess
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env

SR = 44100
_FFMPEG = None
rng = np.random.default_rng(7)


def ffmpeg():
    """懒加载：render.py 里 import 本模块时还没初始化 ffmpeg。"""
    global _FFMPEG
    if not _FFMPEG:
        _FFMPEG = _env.ffmpeg()
    return _FFMPEG


# ---------------------------------------------------------------- 基础
def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def movavg(x, k):
    if k <= 1:
        return x
    return np.convolve(x, np.ones(k) / k, mode="same")


def env_ad(n, a, d, sr=SR):
    e = np.zeros(n)
    na = max(1, int(a * sr))
    nd = max(1, n - na)
    e[:na] = np.linspace(0, 1, na)
    e[na:] = np.exp(-np.arange(nd) / (d * sr))
    return e


def norm(x, peak=0.9):
    m = np.max(np.abs(x)) or 1.0
    return x / m * peak


# ---------------------------------------------------------------- 乐器
def pluck(freq, dur, amp=1.0, decay=5.0, harm=8):
    """拨弦：谐波叠加 + 高次谐波衰减更快，像尤克里里/木吉他"""
    t = t_axis(dur)
    y = np.zeros_like(t)
    for k in range(1, harm + 1):
        y += (1.0 / k ** 1.25) * np.sin(2 * np.pi * freq * k * t + k * 0.7) \
            * np.exp(-t * decay * (1 + 0.40 * k))
    click = rng.uniform(-0.6, 0.6, 48) * np.exp(-np.arange(48) / 10)
    y[:48] += click
    return norm(y, amp)


def kick(dur=0.26):
    t = t_axis(dur)
    f = 128 * np.exp(-t * 24) + 46
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 13)
    return norm(y)


def snare(dur=0.22):
    t = t_axis(dur)
    n = rng.normal(0, 1, len(t))
    y = n * np.exp(-t * 34)
    y -= movavg(y, 18) * 0.7
    y += 0.35 * np.sin(2 * np.pi * 182 * t) * np.exp(-t * 40)
    return norm(y, 0.75)


def hat(dur=0.055):
    t = t_axis(dur)
    y = rng.normal(0, 1, len(t)) * np.exp(-t * 105)
    return norm(y - movavg(y, 10), 0.5)


def shaker(dur=0.08):
    t = t_axis(dur)
    y = rng.normal(0, 1, len(t)) * env_ad(len(t), 0.004, 0.030)
    return norm(y - movavg(y, 6) * 0.85, 0.4)


def bell(freq, dur=0.9, amp=0.6):
    t = t_axis(dur)
    y = np.sin(2 * np.pi * freq * t) * np.exp(-t * 3.4)
    y += 0.45 * np.sin(2 * np.pi * freq * 2.01 * t) * np.exp(-t * 6.0)
    y += 0.20 * np.sin(2 * np.pi * freq * 3.02 * t) * np.exp(-t * 9.0)
    return norm(y, amp)


# ---------------------------------------------------------------- 音效
def sfx_slap():
    """纸片拍到桌面上：脆响 + 低频闷响 + 短褶纸尾"""
    n = int(0.30 * SR)
    y = np.zeros(n)
    m = int(0.045 * SR)
    burst = rng.normal(0, 1, m) * np.exp(-np.arange(m) / (0.010 * SR))
    burst = burst - movavg(burst, 6) * 0.5
    y[:m] += norm(burst, 0.85)
    t = np.arange(n) / SR
    y += 0.55 * np.sin(2 * np.pi * 62 * t) * np.exp(-t * 26)
    cr = rng.normal(0, 1, n) * np.exp(-t * 26) * 0.13
    y += cr - movavg(cr, 5) * 0.6
    return norm(y, 0.85)


def sfx_whoosh(dur=0.42):
    t = t_axis(dur)
    n = rng.normal(0, 1, len(t))
    e = np.sin(np.pi * (t / dur) ** 0.75) ** 1.6
    y = movavg(n, 26) * e
    y += movavg(n, 6) * e * 0.35 * (t / dur)
    return norm(y, 0.5)


def sfx_riser(dur=0.55):
    t = t_axis(dur)
    n = rng.normal(0, 1, len(t))
    e = (t / dur) ** 2.2
    y = movavg(n, 40) * e + movavg(n, 5) * e * 0.5
    return norm(y, 0.45)


def sfx_rip(dur=0.34):
    t = t_axis(dur)
    n = rng.normal(0, 1, len(t))
    am = 0.45 + 0.55 * np.abs(np.sin(2 * np.pi * 46 * t + rng.normal(0, 0.4)))
    y = (n - movavg(n, 8) * 0.6) * am * np.exp(-t * 4.5)
    return norm(y, 0.42)


def sfx_tape(dur=0.20):
    t = t_axis(dur)
    n = rng.normal(0, 1, len(t))
    y = (n - movavg(n, 12) * 0.7) * np.exp(-t * 15)
    return norm(y, 0.35)


SFX_BANK = {"slap": sfx_slap, "whoosh": sfx_whoosh, "riser": sfx_riser,
            "rip": sfx_rip, "tape": sfx_tape,
            "bell": lambda: bell(1046.5, 1.0, 0.55)}


# ---------------------------------------------------------------- BGM
NOTE = {"C3": 130.81, "D3": 146.83, "E3": 164.81, "F3": 174.61, "G3": 196.00,
        "A3": 220.00, "B3": 246.94, "C4": 261.63, "D4": 293.66, "E4": 329.63,
        "F4": 349.23, "G4": 392.00, "A4": 440.00, "B4": 493.88,
        "C5": 523.25, "D5": 587.33, "E5": 659.25, "G5": 783.99, "A5": 880.00}

CHORDS = {"C": ["C4", "E4", "G4", "C5"],
          "G": ["B3", "D4", "G4", "B4"],
          "Am": ["A3", "C4", "E4", "A4"],
          "F": ["A3", "C4", "F4", "A4"],
          "Dm": ["A3", "D4", "F4", "A4"],
          "Em": ["B3", "E4", "G4", "B4"]}
ROOT = {"C": "C3", "G": "G3", "Am": "A3", "F": "F3", "Dm": "D3", "Em": "E3"}
PROG = ["C", "G", "Am", "F", "C", "G", "F", "G", "C", "G", "Am", "F", "C", "G", "C"]


def build_bgm(total_dur, bpm=112, mood="bright"):
    """mood: bright（明亮弹拨）/ calm（去掉鼓，只剩拨弦和铃）"""
    beat = 60.0 / bpm
    bar = beat * 4
    n = int((total_dur + 2.0) * SR)
    L = np.zeros(n)
    R = np.zeros(n)
    drums = mood != "calm"

    def add_st(sig, at, gain=1.0, pan=0.0):
        i = int(at * SR)
        if i >= len(L) or i < 0:
            return
        m = min(len(sig), len(L) - i)
        L[i:i + m] += sig[:m] * gain * (1 - pan * 0.5)
        R[i:i + m] += sig[:m] * gain * (1 + pan * 0.5)

    strum_pat = [(0.0, 1.00), (1.0, 0.55), (1.5, 0.62), (2.0, 0.80),
                 (2.5, 0.50), (3.0, 0.72), (3.5, 0.58)]

    for bi, ch in enumerate(PROG):
        b0 = bi * bar
        if b0 > total_dur + 1.0:
            break
        notes = CHORDS[ch]
        for pos, vel in strum_pat:
            at = b0 + pos * beat
            for j, nm in enumerate(notes):
                add_st(pluck(NOTE[nm], 0.75, amp=0.55 * vel, decay=4.2),
                       at + j * 0.011, gain=0.34, pan=(j - 1.5) * 0.10)
        for pos in (0.0, 2.0, 3.5):
            add_st(pluck(NOTE[ROOT[ch]], 0.5, amp=0.8, decay=6.0, harm=4),
                   b0 + pos * beat, gain=0.29)
        if drums:
            add_st(kick(), b0, 0.45)
            add_st(kick(), b0 + 2 * beat, 0.38)
            add_st(snare(), b0 + 1 * beat, 0.30, pan=0.08)
            add_st(snare(), b0 + 3 * beat, 0.30, pan=0.08)
            for e in np.arange(0, 4, 0.5):
                add_st(shaker(), b0 + e * beat, 0.16 if e % 1 else 0.22, pan=-0.25)
                if e % 1 == 0.5:
                    add_st(hat(), b0 + e * beat, 0.13, pan=0.28)
        if bi % 8 in (3, 4, 6):
            for k, nm in enumerate(notes[::-1][:2]):
                add_st(bell(NOTE[nm] * 2, 0.7, 0.30),
                       b0 + (3.0 - k * 0.5) * beat, 0.5, pan=0.3 - k * 0.4)

    mix = np.stack([L, R])
    hp = lambda x: x - movavg(x, int(SR / 35))     # 剪掉 35Hz 以下的浑浊
    mix = np.stack([hp(mix[0]), hp(mix[1])])
    mix = np.tanh(mix * 0.9)
    return norm(mix, 0.85)[:, :n]


# ---------------------------------------------------------------- 解码
def decode(path):
    p = subprocess.run([ffmpeg(), "-v", "error", "-i", path, "-f", "f32le",
                        "-ac", "1", "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(p.stdout, dtype=np.float32)


def decode_st(path):
    """解成立体声 f32，返回 (2, n)。单声道源会被复制成两声道。"""
    p = subprocess.run([ffmpeg(), "-v", "error", "-i", path, "-f", "f32le",
                        "-ac", "2", "-ar", str(SR), "-"], capture_output=True)
    x = np.frombuffer(p.stdout, dtype=np.float32)
    if x.size == 0:
        return np.zeros((2, 0))
    return x.reshape(-1, 2).T


def load_music_file(path, dur, start=0.0, fade_in=0.35, fade_out=1.6,
                    target_rms=0.085):
    """读外部音乐，从 start 秒起截 dur 秒；不够长就无缝循环。

    循环点接缝做 60ms 交叉淡化，避免咔哒。返回 (2, n)。
    外部曲子母带响度各不相同，先按 RMS 归一到 target_rms，
    这样 `bgm.gain` 的语义对合成和外部音乐是一致的。
    """
    src = decode_st(path)
    if src.shape[1] == 0:
        raise RuntimeError(f"音乐解不出来：{path}")
    n = int(dur * SR) + 1
    a = int(max(0.0, start) * SR)
    seg = src[:, a:] if a < src.shape[1] else src
    if seg.shape[1] < n:
        body, xf = seg, int(0.06 * SR)
        out = [body]
        have = body.shape[1]
        while have < n:
            tail, head = out[-1][:, -xf:], body[:, :xf]
            ramp = np.linspace(0, 1, min(xf, tail.shape[1], head.shape[1]))
            mixin = tail * (1 - ramp) + head * ramp
            out[-1] = np.concatenate([out[-1][:, :-len(ramp)], mixin], axis=1)
            out.append(body[:, len(ramp):])
            have += body.shape[1] - len(ramp)
        seg = np.concatenate(out, axis=1)
    seg = seg[:, :n]
    if seg.shape[1] < n:
        seg = np.pad(seg, ((0, 0), (0, n - seg.shape[1])))

    r = float(np.sqrt((seg ** 2).mean()))
    if r > 1e-6:
        seg = seg * (target_rms / r)
    pk = float(np.abs(seg).max())
    if pk > 0.95:
        seg = seg * (0.95 / pk)

    fi, fo = min(int(fade_in * SR), n), min(int(fade_out * SR), n)
    if fi:
        seg[:, :fi] *= np.linspace(0, 1, fi)
    if fo:
        seg[:, -fo:] *= np.linspace(1, 0, fo)
    return seg


# ---------------------------------------------------------------- 混音
def build_mix(proj, doc, events, out_name="mix.wav"):
    total = events["total_dur"]
    n = int(total * SR) + 1
    vo = np.zeros(n)
    bg = np.zeros((2, n))
    fx = np.zeros(n)
    head = float(doc.get("voice", {}).get("head", 0.24))

    for b in doc["beats"]:
        p = b.get("narration_audio")
        if not p:
            continue
        sig = decode(_env.resolve(proj, p))
        if sig.size == 0:
            print(f"[warn] 第 {b['id']} 拍配音解不出来：{p}", flush=True)
            continue
        sig = norm(sig, 0.92)
        i = int((events["beats"][str(b["id"])] + head) * SR)
        m = min(len(sig), n - i)
        if i < n:
            vo[i:i + m] += sig[:m]

    bgm = doc.get("bgm") or {}
    if bgm.get("enabled", True):
        from_file = bgm.get("source") == "file" and bgm.get("file")
        if from_file:
            mpath = _env.resolve(proj, bgm["file"])
            music = load_music_file(mpath, total, float(bgm.get("start", 0.0)),
                                    float(bgm.get("fade_in", 0.35)),
                                    float(bgm.get("fade_out", 1.6)))
            print(f"bgm <- {os.path.basename(mpath)}  from {bgm.get('start', 0)}s", flush=True)
        else:
            music = build_bgm(total, bgm.get("bpm", 112), bgm.get("mood", "bright"))
        m = min(music.shape[1], n)
        bg[:, :m] = music[:, :m]
        # 侧链：人声包络越强，音乐压得越低
        env = movavg(np.abs(vo), int(0.06 * SR))
        env = env / (np.max(env) or 1.0)
        duck = 1.0 - float(bgm.get("duck", 0.72)) * np.clip(env * 3.2, 0, 1)
        bg *= float(bgm.get("gain", 0.30)) * duck
        if not from_file:
            fi, fo = min(int(0.35 * SR), n), min(int(1.4 * SR), n)
            if fi:
                bg[:, :fi] *= np.linspace(0, 1, fi)
            if fo:
                bg[:, -fo:] *= np.linspace(1, 0, fo)

    cache = {}
    for ev in events["sfx"]:
        kind = ev["type"]
        if kind not in cache:
            cache[kind] = SFX_BANK.get(kind, sfx_whoosh)()
        sig = cache[kind]
        i = int(ev["t"] * SR)
        if i < 0 or i >= n:
            continue
        m = min(len(sig), n - i)
        fx[i:i + m] += sig[:m] * ev.get("gain", 0.6)

    out = np.stack([vo + bg[0] + fx, vo + bg[1] + fx])
    out = np.tanh(out * 1.05)
    # 留 4dB 余量并硬限幅：AAC 编码会在瞬态上过冲，母带顶到 0.94 时解码出来常常破 1.0
    out = np.clip(norm(out, 0.90), -0.95, 0.95)

    wav = os.path.join(proj, "build", out_name)
    os.makedirs(os.path.dirname(wav), exist_ok=True)
    pcm = (np.clip(out.T, -1, 1) * 32767).astype(np.int16)
    with wave.open(wav, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"mix -> {wav}  {total:.2f}s", flush=True)
    return wav


if __name__ == "__main__":
    args = sys.argv[1:]
    proj = next((a for a in args if not a.startswith("--")), ".")

    def opt(name, default=None):
        for i, a in enumerate(args):
            if a == name and i + 1 < len(args):
                return args[i + 1]
            if a.startswith(name + "="):
                return a.split("=", 1)[1]
        return default

    proj, _, doc = _env.load_project(proj)
    bgm = doc.setdefault("bgm", {})
    if "--bgm-off" in args:
        bgm["enabled"] = False
    if opt("--bgm-file"):
        bgm["enabled"] = True
        bgm["source"] = "file"
        bgm["file"] = opt("--bgm-file")
    if opt("--bgm-start") is not None:
        bgm["start"] = float(opt("--bgm-start"))
    if opt("--bgm-gain") is not None:
        bgm["gain"] = float(opt("--bgm-gain"))

    ev = json.load(open(os.path.join(proj, "build", "events.json"), encoding="utf-8"))
    build_mix(proj, doc, ev, out_name=opt("--out", "mix.wav"))
