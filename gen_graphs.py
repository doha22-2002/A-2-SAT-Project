#!/usr/bin/env python3
from __future__ import annotations
import random
import argparse

def write_static_edge_list(path: str, n: int, edges: list[tuple[int,int]]):
    edges = [(u,v) if u < v else (v,u) for (u,v) in edges if u != v]
    edges = sorted(set(edges))
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{n} {len(edges)}\n")
        for u,v in edges:
            f.write(f"{u} {v}\n")

def gen_gnp(n: int, p: float, seed: int) -> list[tuple[int,int]]:
    rng = random.Random(seed)
    edges = []
    for u in range(1, n+1):
        for v in range(u+1, n+1):
            if rng.random() < p:
                edges.append((u,v))
    return edges

def gen_sparse_linear(n: int) -> list[tuple[int,int]]:
    # path + a few chords (still sparse)
    edges = [(i, i+1) for i in range(1, n)]
    for i in range(1, n-10, 10):
        edges.append((i, i+10))
    return edges

def gen_complete(n: int) -> list[tuple[int,int]]:
    return [(u,v) for u in range(1,n+1) for v in range(u+1,n+1)]

def gen_complete_bipartite(a: int, b: int) -> tuple[int, list[tuple[int,int]]]:
    n = a + b
    left = list(range(1, a+1))
    right = list(range(a+1, a+b+1))
    edges = [(u,v) for u in left for v in right]
    return n, edges

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="bench_graphs")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    import os
    os.makedirs(args.outdir, exist_ok=True)

    # Large sparse
    write_static_edge_list(f"{args.outdir}/large_sparse_n5000.txt", 5000, gen_sparse_linear(5000))

    # Medium random sparse
    write_static_edge_list(f"{args.outdir}/gnp_n2000_p0.003.txt", 2000, gen_gnp(2000, 0.003, args.seed))

    # Medium random dense-ish (careful: can be heavy)
    write_static_edge_list(f"{args.outdir}/gnp_n800_p0.08.txt", 800, gen_gnp(800, 0.08, args.seed))

    # Fallback triggers
    write_static_edge_list(f"{args.outdir}/K120.txt", 120, gen_complete(120))  # degeneracy=119 -> fallback by k>80
    n, e = gen_complete_bipartite(200, 200)
    write_static_edge_list(f"{args.outdir}/K200_200.txt", n, e)  # dense but triangle-free

    print("Wrote graphs to:", args.outdir)

if __name__ == "__main__":
    main()
