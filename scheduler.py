#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地定时调度器：每 2 小时的第 37 分钟准时执行 vpngate.py。

目标时刻（本地时间）：00:37 / 02:37 / 04:37 / 06:37 / 08:37 / 10:37
                     12:37 / 14:37 / 16:37 / 18:37 / 20:37 / 22:37

设计要点：
  * 严格按"下一个目标时刻"计算睡眠，不会因上次运行耗时而漂移。
  * 只使用本项目 .venv 内的 Python 与 requests，零全局污染。
  * CHECK_WORKER 默认已填真实 Worker 域名，可用环境变量覆盖。
"""
import os
import sys
import time
import subprocess
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHECK_WORKER = os.environ.get(
    "CHECK_WORKER",
    "https://jiance.relyon.indevs.in/check?sstp=vpn:vpn@",
)

TARGET_MINUTE = 37
TARGET_HOUR_STEP = 2  # 每 2 小时

# git push 到 github.com 必须走本地代理（直连会被重置）
GIT_PROXY = os.environ.get("GIT_PROXY", "http://127.0.0.1:10808")


def next_run_time(now: datetime) -> datetime:
    """返回下一个目标运行时刻（本地时间，精确到 37 分 0 秒）。"""
    cand = now.replace(minute=TARGET_MINUTE, second=0, microsecond=0)
    if cand <= now:
        cand += timedelta(hours=1)
    while cand.hour % TARGET_HOUR_STEP != 0:
        cand += timedelta(hours=1)
    return cand


def git_push():
    """把 public/ 推送到 GitHub Pages（分支部署）。"""
    git = "git"
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    # 走本地代理，否则 github.com 直连会被重置（Empty reply from server）
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        env[k] = GIT_PROXY
    env.pop("NO_PROXY", None)
    env.pop("no_proxy", None)

    token = ""
    token_file = os.path.join(BASE_DIR, ".git_token")
    if os.path.exists(token_file):
        token = open(token_file, encoding="utf-8").read().strip()
    push_url = (
        f"https://Moral912:{token}@github.com/Moral912/gate.git"
        if token
        else "https://github.com/Moral912/gate.git"
    )

    def run(args):
        return subprocess.run(args, cwd=BASE_DIR, env=env, check=False)

    run([git, "add", "docs"])
    # 没有变更就跳过
    if run([git, "diff", "--cached", "--quiet"]).returncode == 0:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] docs/ 无变更, 跳过 push", flush=True)
        return
    run([
        git, "-c", "user.name=Moral912", "-c", "user.email=2936477497@qq.com",
        "commit", "-m", f"update nodes {datetime.now():%Y%m%d-%H%M}",
    ])
    r = run([git, "push", push_url, "HEAD:main"])
    # 失败时重试 2 次（网络抖动/代理未就绪）
    for attempt in range(1, 3):
        if r.returncode == 0:
            break
        print(
            f"[{datetime.now():%Y-%m-%d %H:%M:%S}] push 失败, 第 {attempt} 次重试...",
            flush=True,
        )
        time.sleep(10)
        r = run([git, "push", push_url, "HEAD:main"])
    print(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] git push 返回码={r.returncode}",
        flush=True,
    )


def run_once():
    env = dict(os.environ)
    env["CHECK_WORKER"] = CHECK_WORKER
    env["PUBLIC_DIR"] = os.path.join(BASE_DIR, "docs")
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] >>> 开始执行 vpngate.py", flush=True)
    t0 = time.time()
    r = subprocess.run(
        [sys.executable, os.path.join(BASE_DIR, "vpngate.py")],
        env=env,
        cwd=BASE_DIR,
    )
    dt = time.time() - t0
    print(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] <<< 执行结束 "
        f"返回码={r.returncode} 耗时={dt:.1f}s",
        flush=True,
    )
    if r.returncode == 0:
        git_push()
    else:
        print(
            f"[{datetime.now():%Y-%m-%d %H:%M:%S}] vpngate.py 失败, 跳过 push",
            flush=True,
        )


def main():
    print(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 调度器启动 "
        f"(目标: 每 {TARGET_HOUR_STEP} 小时的 :{TARGET_MINUTE:02d} 分, 本地时间)",
        flush=True,
    )
    while True:
        target = next_run_time(datetime.now())
        wait = (target - datetime.now()).total_seconds()
        print(
            f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 下次运行: "
            f"{target:%Y-%m-%d %H:%M:%S} ({wait / 60:.1f} 分钟后)",
            flush=True,
        )
        if wait > 0:
            time.sleep(wait)
        # 精确卡到目标整点边界再执行
        while datetime.now() < target:
            time.sleep(0.2)
        run_once()
        time.sleep(1)  # 防止同一秒重复触发


if __name__ == "__main__":
    main()
