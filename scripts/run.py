#!/usr/bin/env python3
"""一条命令跑完整条管线：配音 → 逐帧渲染 + 混音 → 自检。

前置：beats.json 已写好，海报已就位（keyframes/）。

用法:
  python run.py <project_dir>               全流程
  python run.py <project_dir> --no-tts      只重渲画面（文案没改，省一次配音）
  python run.py <project_dir> --size 1920x1080
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(script, *args):
    cmd = [sys.executable, os.path.join(HERE, script), *args]
    print(f"\n>>> {script} {' '.join(args)}", flush=True)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit(f"{script} 失败（exit {r.returncode}）")


def main():
    args = sys.argv[1:]
    proj = args[0] if args and not args[0].startswith("-") else "."
    proj = os.path.abspath(proj)
    if "--no-tts" not in args:
        run("tts.py", proj)
    render_args = [proj]
    if "--size" in args:
        render_args += ["--size", args[args.index("--size") + 1]]
    run("render.py", *render_args)
    run("verify.py", proj)


if __name__ == "__main__":
    main()
