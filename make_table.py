from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional, Literal, Tuple

Mode = Literal["static", "temporal"]


@dataclass
class TestCase:
    name: str
    path: str
    mode: Mode
    expected: Optional[bool]   # True / False / None


DEFAULT_TESTS: List[TestCase] = [
    # ---- Static graphs ----
    TestCase("C4", "C4.txt", "static", True),
    TestCase("C6", "C6.txt", "static", True),
    TestCase("C7", "C7.txt", "static", False),
    TestCase("C9", "C9.txt", "static", False),
    TestCase("C5", "cycle5.txt", "static", False),

    TestCase("Path P4", "path4.txt", "static", True),
    TestCase("Star n=6", "star6.txt", "static", True),
    TestCase("Triangle K3", "triangle.txt", "static", True),

    TestCase("Clique K6", "K6.txt", "static", True),
    TestCase("Bipartite K3,3", "K33.txt", "static", True),
    TestCase("Bipartite K4,4", "K44.txt", "static", True),

    TestCase("House", "house.txt", "static", True),
    TestCase("Disconnected mix", "disconnectedMix.txt", "static", True),

    TestCase("Large sparse", "largeSparse.txt", "static", None),
    TestCase("Medium dense", "mediDense.txt", "static", None),
    TestCase("Realistic sparse", "realisticSparse.txt", "static", None),

    # ---- Temporal graphs ----
    TestCase("Temporal small pathlike", "temporal_sat_small_pathlike.txt", "temporal", True),
    TestCase("Temporal hard K6 aug", "temporal_hard_K6_aug.txt", "temporal", False),
]




_RE_SAT = re.compile(r"SAT\s*\(.*\)\s*:\s*(True|False)", re.IGNORECASE)
_RE_NM = re.compile(r"\bn\s*=\s*(\d+)\s+m\s*=\s*(\d+)\b", re.IGNORECASE)
_RE_CLAUSES = re.compile(r"generated\s+clauses\s*=\s*(\d+)", re.IGNORECASE)

# static-only
_RE_K = re.compile(r"degeneracy\s+k\s*=\s*(-?\d+)", re.IGNORECASE)
_RE_FALLBACK = re.compile(r"used\s+fallback\s*=\s*(True|False)", re.IGNORECASE)



def run_solver(
    solver_py: str,
    test: TestCase,
    png_dir: str,
) -> Tuple[bool, int, int, Optional[int], int, Optional[bool]]:


    os.makedirs(png_dir, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", test.name)
    png_path = os.path.join(png_dir, f"{safe}.png")

    cmd = [
        sys.executable,
        solver_py,
        "--graph", test.path,
        "--stats",
        "--png", png_path,
    ]

    if test.mode == "temporal":
        cmd += ["--mode", "temporal"]
    else:
        cmd += ["--mode", "static"]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")

    m_sat = _RE_SAT.search(out)
    m_nm = _RE_NM.search(out)
    m_cl = _RE_CLAUSES.search(out)

    if not (m_sat and m_nm and m_cl):
        raise RuntimeError(
            f"Cannot parse output for {test.name}\n"
            f"---- OUTPUT ----\n{out}"
        )

    sat = (m_sat.group(1).lower() == "true")
    n = int(m_nm.group(1))
    m = int(m_nm.group(2))
    clauses = int(m_cl.group(1))

    if test.mode == "static":
        mk = _RE_K.search(out)
        mfb = _RE_FALLBACK.search(out)
        if not (mk and mfb):
            raise RuntimeError(
                f"Static output missing degeneracy/fallback for {test.name}"
            )
        k = int(mk.group(1))
        fb = (mfb.group(1).lower() == "true")
        return sat, n, m, k, clauses, fb

    # temporal mode
    return sat, n, m, None, clauses, None



def write_markdown(rows: List[dict], path: str) -> None:
    headers = ["Graph", "n", "m", "Expected", "Result", "Correct",
               "Degeneracy", "Clauses", "Fallback"]
    with open(path, "w", encoding="utf-8") as f:
        f.write("| " + " | ".join(headers) + " |\n")
        f.write("|" + "|".join(["---"] * len(headers)) + "|\n")
        for r in rows:
            f.write("| " + " | ".join(str(r[h]) for h in headers) + " |\n")



def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solver", required=True, help="Path to main6.py")
    ap.add_argument("--out", default="results.csv")
    ap.add_argument("--md", default="results.md")
    ap.add_argument("--png-dir", default="png_out")
    args = ap.parse_args()

    rows: List[dict] = []
    known_total = 0
    known_correct = 0

    for test in DEFAULT_TESTS:
        if not os.path.exists(test.path):
            print(f"[SKIP] missing {test.path}")
            continue

        try:
            sat, n, m, k, clauses, fb = run_solver(
                solver_py=args.solver,
                test=test,
                png_dir=args.png_dir,
            )
        except Exception as e:
            print(f"[ERROR] {test.name}: {e}")
            continue

        expected = "?" if test.expected is None else ("True" if test.expected else "False")
        result = "True" if sat else "False"

        if test.expected is None:
            correct = "N/A"
        else:
            known_total += 1
            ok = (sat == test.expected)
            if ok:
                known_correct += 1
            correct = "Yes" if ok else "No"

        rows.append({
            "Graph": test.name,
            "n": n,
            "m": m,
            "Expected": expected,
            "Result": result,
            "Correct": correct,
            "Degeneracy": "N/A" if k is None else k,
            "Clauses": clauses,
            "Fallback": "N/A" if fb is None else ("Yes" if fb else "No"),
        })

    # CSV
    headers = ["Graph", "n", "m", "Expected", "Result",
               "Correct", "Degeneracy", "Clauses", "Fallback"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # Markdown
    write_markdown(rows, args.md)

    print(f"[DONE] wrote {args.out} and {args.md}")
    print(f"[PNGs] saved in {args.png_dir}/")

    if known_total > 0:
        acc = 100.0 * known_correct / known_total
        print(f"[ACCURACY] {known_correct}/{known_total} = {acc:.1f}%")


if __name__ == "__main__":
    main()
