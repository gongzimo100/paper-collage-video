#!/usr/bin/env python3
"""环境自检。跑任何片之前先跑这个，30 秒排掉 90% 的"跑到一半才报错"。

用法:
  python doctor.py               只检查
  python doctor.py --install     缺什么装什么（pip）
"""
import importlib
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env

PKGS = [("PIL", "pillow", "图像合成"), ("numpy", "numpy", "音频合成"),
        ("edge_tts", "edge-tts", "中文配音"), ("imageio_ffmpeg", "imageio-ffmpeg", "ffmpeg 兜底")]


def main():
    install = "--install" in sys.argv
    ok = True

    print("== Python 包 ==")
    missing = []
    for mod, pip_name, why in PKGS:
        try:
            importlib.import_module(mod)
            print(f"  [ok]   {pip_name:<14} {why}")
        except Exception:
            print(f"  [miss] {pip_name:<14} {why}")
            missing.append(pip_name)
    if missing:
        ok = False
        if install:
            print("  -> pip install " + " ".join(missing))
            subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", *missing])

    print("== ffmpeg ==")
    try:
        ff = _env.ffmpeg()
        v = subprocess.run([ff, "-version"], capture_output=True, text=True,
                           errors="ignore").stdout.splitlines()[0]
        print(f"  [ok]   {ff}")
        print(f"         {v[:70]}")
    except SystemExit as e:
        ok = False
        print(f"  [fail] {e}")

    print("== 中文字体 ==")
    fb, fr = _env.font_bold(), _env.font_regular()
    print(f"  [{'ok' if fb else 'warn'}]   粗体 {fb or '未找到（标题会变方块）'}")
    print(f"  [{'ok' if fr else 'warn'}]   常规 {fr or '未找到'}")
    if not fb:
        ok = False

    print("== 配音连通性 ==")
    try:
        import asyncio
        import edge_tts
        tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".probe.mp3")
        asyncio.run(edge_tts.Communicate("测试", "zh-CN-YunxiNeural").save(tmp))
        size = os.path.getsize(tmp)
        os.remove(tmp)
        print(f"  [ok]   edge-tts 出音正常（{size} bytes）")
    except Exception as e:
        ok = False
        print(f"  [fail] 配音不通：{e}（检查网络能否访问 speech.platform.bing.com）")

    print("\n" + ("全部就绪，可以开工。" if ok else "有项目没通过，先修上面的 [miss]/[fail]。"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
