#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import re
from typing import Dict, List, Optional, Tuple
import os

# plotting
import matplotlib.pyplot as plt


RE_SAT = re.compile(r"SAT\s*\(.*\)\s*:\s*(True|False)", re.IGNORECASE)
RE_CLAUSES = re.compile(r"generated\s+clauses\s*=\s*(\d+)", re.IGNORECASE)
RE_K = re.compile(r"degeneracy\s+k\s*=\s*(-?\d+)", re.IGNORECASE)
RE_FALLBACK = re.compile(r"used\s+fallback\s*=\s*(True|False)", re.IGNORECASE)

def parse_solver_output(out: str) -> Dict:
    d: Dict = {}
    m = RE_SAT.search(out)
    d["sat"] = m.group(1) if m else "?"
    m = RE_CLAUSES.search(out)
    d["clauses"] = int(m.group(1)) if m else -1
    m = RE_K.search(out)
    d["k"] = int(m.group(1)) if m else None
    m = RE_FALLBACK.search(out)
    d["fallback"] = (m.group(1).lower() == "true") if m else None
    return d


def run_solver_once(
    solver: str,
    graph: str,
    mode: str,
    extra: List[str],
    measure_rss: bool,
    sample_ms: int,
) -> Tuple[float, int, str, Optional[float]]:

    cmd = [sys.executable, solver, "--graph", graph, "--mode", mode, "--stats"] + extra

    if not measure_rss:
        t0 = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        dt = time.perf_counter() - t0
        out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        return dt, proc.returncode, out, None

    import psutil

    t0 = time.perf_counter()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    child = psutil.Process(p.pid)

    peak_rss = 0
    sleep_s = max(1, sample_ms) / 1000.0

    while True:
        if p.poll() is not None:
            break
        try:
            rss = child.memory_info().rss
            peak_rss = max(peak_rss, rss)
        except psutil.Error:
            pass
        time.sleep(sleep_s)

    out, err = p.communicate()
    dt = time.perf_counter() - t0
    combined = (out or "") + ("\n" + err if err else "")

    return dt, p.returncode, combined, peak_rss / (1024 * 1024)


def save_time_plot(times: List[float], meta: Dict, out_png: str):
    x = list(range(1, len(times) + 1))
    plt.figure(figsize=(10, 5))
    plt.plot(x, times, marker="o", linewidth=2)
    plt.xticks(x)
    plt.xlabel("Repeat")
    plt.ylabel("Time (seconds)")
    plt.title("Benchmark Runtime per Run")

    for xi, ti in zip(x, times):
        plt.annotate(f"{ti:.3f}s", (xi, ti), xytext=(0, 8),
                     textcoords="offset points", ha="center")

    text = "\n".join([
        f"graph: {meta['graph']}",
        f"mode: {meta['mode']}",
        f"SAT: {meta['sat']}",
        f"clauses: {meta['clauses']}",
        f"k: {meta['k']}",
        f"fallback: {meta['fallback']}",
        f"avg/min/max: {sum(times)/len(times):.3f} / {min(times):.3f} / {max(times):.3f} s"
    ])
    plt.gcf().text(0.68, 0.25, text, fontsize=9, va="top")

    plt.tight_layout(rect=[0, 0, 0.65, 1])
    plt.savefig(out_png, dpi=200)
    plt.close()

def save_rss_plot(rss: List[float], meta: Dict, out_png: str):
    x = list(range(1, len(rss) + 1))
    plt.figure(figsize=(10, 5))
    plt.plot(x, rss, marker="o", linewidth=2)
    plt.xticks(x)
    plt.xlabel("Repeat")
    plt.ylabel("Peak RSS (MB)")
    plt.title("Solver Peak RSS per Run")

    for xi, mi in zip(x, rss):
        plt.annotate(f"{mi:.2f} MB", (xi, mi), xytext=(0, 8),
                     textcoords="offset points", ha="center")

    text = "\n".join([
        f"graph: {meta['graph']}",
        f"mode: {meta['mode']}",
        f"avg/max RSS: {sum(rss)/len(rss):.2f} / {max(rss):.2f} MB"
    ])
    plt.gcf().text(0.70, 0.25, text, fontsize=9, va="top")

    plt.tight_layout(rect=[0, 0, 0.68, 1])
    plt.savefig(out_png, dpi=200)
    plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solver", default="main6.py")
    ap.add_argument("--graph", required=True)
    ap.add_argument("--mode", choices=["static", "temporal"], default="static")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--extra", nargs="*", default=[])
    ap.add_argument("--rss", action="store_true")
    ap.add_argument("--sample-ms", type=int, default=10)
    ap.add_argument("--out-prefix", default="bench_result")
    args = ap.parse_args()

    times: List[float] = []
    rss_peaks: List[float] = []
    last: Optional[Dict] = None

    graph_abs = os.path.abspath(args.graph)

    for _ in range(args.repeat):
        dt, code, out, rss = run_solver_once(
            args.solver, graph_abs, args.mode,
            args.extra, args.rss, args.sample_ms
        )
        if code != 0:
            print(out)
            raise SystemExit(code)

        last = parse_solver_output(out)
        times.append(dt)
        if rss is not None:
            rss_peaks.append(rss)

    assert last is not None

    meta = {
        "graph": os.path.basename(graph_abs),
        "mode": args.mode,
        "sat": last["sat"],
        "clauses": last["clauses"],
        "k": last["k"],
        "fallback": last["fallback"],
    }

    # Save plots
    save_time_plot(times, meta, args.out_prefix + "_time.png")
    if args.rss:
        save_rss_plot(rss_peaks, meta, args.out_prefix + "_rss.png")

    print("PNG saved:")
    print(" ", args.out_prefix + "_time.png")
    if args.rss:
        print(" ", args.out_prefix + "_rss.png")

if __name__ == "__main__":
    main()
