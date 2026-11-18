#!/usr/bin/env python3
"""抽帧看构图。出片后必做的一步——数字指标过了，画面未必好看。

用法: python frame.py <project_dir> [时刻...]
      不给时刻就自动抽每拍的中点。
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env


def main():
    args = [a for a in sys.argv[1:]]
    proj, bpath, doc = _env.load_project(args[0] if args else ".")
    final = os.path.join(proj, doc.get("output", "final.mp4"))
    if not os.path.isfile(final):
        raise SystemExit(f"还没出片：{final}")

    times = []
    for a in args[1:]:
        try:
            times.append(float(a))
        except ValueError:
            pass
    if not times:                                    # 默认抽每拍中点（标题和字幕都已就位）
        t = 0.0
        for b in doc["beats"]:
            times.append(round(t + float(b["dur"]) * 0.62, 2))
            t += float(b["dur"])

    out = os.path.join(proj, "build")
    os.makedirs(out, exist_ok=True)
    ff = _env.ffmpeg()
    for t in times:
        dst = os.path.join(out, f"frame_{t}.png")
        subprocess.run([ff, "-y", "-loglevel", "error", "-ss", str(t), "-i", final,
                        "-frames:v", "1", dst], check=True)
        print(dst, flush=True)


if __name__ == "__main__":
    main()
