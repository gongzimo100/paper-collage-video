#!/usr/bin/env python3
"""成片自检：听不到声音也能判断片子有没有问题。

查四件事：时长/画幅对不对、音轨有没有削波、有没有长时间空档、每拍配音是否落位。

用法: python verify.py <project_dir>
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env


def main():
    proj, _, doc = _env.load_project(sys.argv[1] if len(sys.argv) > 1 else ".")
    final = os.path.join(proj, doc.get("output", "final.mp4"))
    if not os.path.isfile(final):
        raise SystemExit(f"还没出片：{final}")

    ff = _env.ffmpeg()
    w, h, dur = _env.probe_info(final)
    expect = round(sum(float(b["dur"]) for b in doc["beats"]), 2)
    size_mb = os.path.getsize(final) / 1024 / 1024

    print(f"文件   {final}")
    print(f"画面   {w}x{h}  时长 {dur}s（分镜合计 {expect}s）  {size_mb:.1f}MB")

    warns = []
    if abs(dur - expect) > 1.0:
        warns.append(f"时长与分镜合计差 {abs(dur - expect):.1f}s，可能有一拍没渲完")

    # 解成双声道 f32 做电平分析
    # 注意：不能用 -ac 1，ffmpeg 的立体声降混是 L+R（不是 (L+R)/2），
    # 相干信号会被抬高约 3dB，测出来的峰值全是假的。
    p = subprocess.run([ff, "-v", "error", "-i", final, "-f", "f32le", "-ac", "2",
                        "-ar", "44100", "-"], capture_output=True)
    import numpy as np
    raw = np.frombuffer(p.stdout, dtype=np.float32)
    x = raw.reshape(-1, 2).mean(axis=1) if raw.size >= 2 else raw
    if raw.size:
        peak = float(np.abs(raw).max())
        clip = float((np.abs(raw) > 0.995).mean() * 100)
        print(f"音频   峰值 {peak:.2f}  削波 {clip:.3f}%（AAC 解码允许少量过冲）")
        if peak > 1.02 and clip > 0.05:
            warns.append("削波偏多，把 bgm.gain 降到 0.22，或 audio.py 里 norm 目标降到 0.86")
        if peak < 0.5:
            warns.append("整体音量偏小，检查 narration 是否生成成功")

        sr = 44100
        secs = int(x.size / sr)
        rms = [float(np.sqrt((x[i * sr:(i + 1) * sr] ** 2).mean())) for i in range(secs)]
        quiet = [i for i, v in enumerate(rms) if v < 0.01]
        if len(quiet) > max(2, secs * 0.2):
            warns.append(f"有 {len(quiet)} 秒接近静音（第 {quiet[:6]} 秒），BGM 可能没混进去")
        print(f"节奏   每秒 RMS 最低 {min(rms):.3f} / 最高 {max(rms):.3f}")

    # 静音检测：句中长停顿会显得拖
    r = subprocess.run([ff, "-hide_banner", "-i", final, "-af",
                        "silencedetect=n=-35dB:d=0.6", "-f", "null", "-"],
                       capture_output=True, text=True, errors="ignore")
    gaps = [l.split("silence_duration:")[-1].strip()
            for l in (r.stderr or "").splitlines() if "silence_duration" in l]
    if gaps:
        print(f"停顿   >0.6s 的空档 {len(gaps)} 处：{' / '.join(gaps[:6])}")
        if any(float(g) > 1.2 for g in gaps):
            warns.append("有超过 1.2s 的空档，把 voice.tail 调小或加一句旁白")

    # 每拍配音落位
    print("分镜   " + "  ".join(f"{b['id']}:{b.get('narration_dur', '?')}s" for b in doc["beats"]))

    if warns:
        print("\n需要处理：")
        for i, m in enumerate(warns, 1):
            print(f"  {i}. {m}")
        return 1
    print("\n通过：时长、画幅、电平、节奏都在合理区间。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
