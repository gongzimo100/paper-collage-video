#!/usr/bin/env python3
"""每拍一句旁白 → mp3，量出真实时长写回 beats.json。

配音走 edge-tts（微软 Edge 在线语音，免费、无需 key、国内直连）。
时长用 ffmpeg 解析，不依赖 ffprobe。
写完把 narration_dur / dur / total_dur 全部回写，后续渲染直接照用。

用法: python tts.py <project_dir> [--voice zh-CN-YunxiNeural] [--rate +6%]
"""
import asyncio
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env

FALLBACK_VOICES = ["zh-CN-YunxiNeural", "zh-CN-XiaoxiaoNeural", "zh-CN-YunyangNeural"]


async def _say(text, voice, rate, dest):
    import edge_tts
    for attempt in range(3):
        try:
            await edge_tts.Communicate(text, voice, rate=rate).save(dest)
            if os.path.exists(dest) and os.path.getsize(dest) > 1024:
                return
        except Exception as e:            # 网络抖动 / 该音色临时不可用
            if attempt == 2:
                raise
            print(f"  retry {attempt + 1}: {e}", flush=True)
            await asyncio.sleep(1.2)


def say(text, voice, rate, dest):
    asyncio.run(_say(text, voice, rate, dest))


def trim_silence(src, dest):
    """削掉首尾静音 —— 不削的话每拍前面都拖着半秒空白，节奏立刻散。"""
    flt = ("silenceremove=start_periods=1:start_silence=0.04:start_threshold=-45dB:detection=peak,"
           "areverse,"
           "silenceremove=start_periods=1:start_silence=0.04:start_threshold=-45dB:detection=peak,"
           "areverse")
    subprocess.run([_env.ffmpeg(), "-y", "-loglevel", "error", "-i", src, "-af", flt,
                    "-c:a", "libmp3lame", "-q:a", "3", dest], check=True)


def main():
    args = sys.argv[1:]
    opts, pos, i = {}, [], 0
    while i < len(args):
        a = args[i]
        if a in ("--voice", "--rate"):
            opts[a.lstrip("-")] = args[i + 1]
            i += 2
            continue
        if a.startswith("--voice=") or a.startswith("--rate="):
            k, v = a[2:].split("=", 1)
            opts[k] = v
            i += 1
            continue
        pos.append(a)
        i += 1

    try:
        import edge_tts  # noqa: F401
    except ImportError:
        raise SystemExit("缺 edge-tts：pip install edge-tts  （或 python scripts/doctor.py --install）")

    proj, bpath, doc = _env.load_project(pos[0] if pos else ".")

    voice = doc.setdefault("voice", {})
    voice.setdefault("voice", "zh-CN-YunxiNeural")
    voice.setdefault("rate", "+6%")
    voice.setdefault("head", 0.24)       # 每拍开头留给标题拍入的空档
    voice.setdefault("tail", 1.06)       # 句尾呼吸
    voice.update(opts)

    adir = os.path.join(proj, "audio")
    os.makedirs(adir, exist_ok=True)

    for b in doc["beats"]:
        raw = os.path.join(adir, f"raw_{b['id']}.mp3")
        rel = f"audio/narr_{b['id']}.mp3"
        dest = os.path.join(proj, rel)
        say(b["narration"], voice["voice"], voice["rate"], raw)
        trim_silence(raw, dest)
        b["narration_audio"] = rel                 # 存相对路径，整个项目可搬移
        b["narration_dur"] = round(_env.probe_duration(dest), 3)
        b["dur"] = round(b["narration_dur"] + voice["head"] + voice["tail"], 2)
        print(f"[beat {b['id']}] vo={b['narration_dur']}s  beat={b['dur']}s", flush=True)

    doc["total_dur"] = round(sum(b["dur"] for b in doc["beats"]), 2)
    json.dump(doc, open(bpath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"total {doc['total_dur']}s  ->  {bpath}", flush=True)

    if doc["total_dur"] < 8 or doc["total_dur"] > 90:
        print(f"[hint] 总时长 {doc['total_dur']}s 不在常见区间（8–90s）。"
              "太短多半是字数不够，太长考虑拆成两条。", flush=True)


if __name__ == "__main__":
    main()
