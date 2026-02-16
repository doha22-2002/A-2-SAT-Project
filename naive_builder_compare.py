#!/usr/bin/env python3
from __future__ import annotations
import argparse, time
from collections import defaultdict
from typing import List, Tuple, Dict, Set, Optional



def lit_to_node(lit: int) -> int:
    v = abs(lit) - 1
    return (2 * v) ^ (1 if lit < 0 else 0)

def neg_node(node: int) -> int:
    return node ^ 1

def kosaraju_scc(g: List[List[int]]) -> List[int]:
    n = len(g)
    gr = [[] for _ in range(n)]
    for u in range(n):
        for v in g[u]:
            gr[v].append(u)

    vis = [False]*n
    order = []
    for s in range(n):
        if vis[s]: continue
        st = [(s,0)]
        vis[s] = True
        while st:
            u,i = st[-1]
            if i < len(g[u]):
                v = g[u][i]
                st[-1] = (u,i+1)
                if not vis[v]:
                    vis[v] = True
                    st.append((v,0))
            else:
                st.pop()
                order.append(u)

    comp = [-1]*n
    cid = 0
    for s in reversed(order):
        if comp[s] != -1: continue
        q = [s]
        comp[s] = cid
        while q:
            u = q.pop()
            for v in gr[u]:
                if comp[v] == -1:
                    comp[v] = cid
                    q.append(v)
        cid += 1
    return comp

class TwoSAT:
    def __init__(self, nvars: int):
        self.n = nvars
        self.g = [[] for _ in range(2*nvars)]
        self.clauses = 0

    def add_clause(self, a: int, b: int):
        ua = lit_to_node(a)
        ub = lit_to_node(b)
        self.g[neg_node(ua)].append(ub)
        self.g[neg_node(ub)].append(ua)
        self.clauses += 1

    def solve(self) -> bool:
        comp = kosaraju_scc(self.g)
        for i in range(self.n):
            if comp[2*i] == comp[2*i+1]:
                return False
        return True

def read_edge_list(path: str) -> Tuple[int, List[Tuple[int,int]]]:
    edges = []
    with open(path,"r",encoding="utf-8") as f:
        n,m = map(int,f.readline().split())
        for _ in range(m):
            u,v = map(int,f.readline().split())
            if u==v: continue
            if u>v: u,v=v,u
            edges.append((u,v))
    edges = sorted(set(edges))
    return n, edges

def naive_o_n3_builder(n: int, edges: List[Tuple[int,int]]) -> Tuple[bool, int]:
    # adjacency matrix for O(1) edge queries
    adj = [[False]*(n+1) for _ in range(n+1)]
    for u,v in edges:
        adj[u][v] = adj[v][u] = True

    # map edge -> var id
    eid: Dict[Tuple[int,int], int] = {}
    for idx,(u,v) in enumerate(edges, start=1):
        eid[(u,v)] = idx

    def var(u:int,v:int)->int:
        if u<v: return eid[(u,v)]
        return eid[(v,u)]

    def lit_orient(u:int,v:int)->int:
        x = var(u,v)
        return +x if u < v else -x

    ts = TwoSAT(len(edges))

    # Naive induced P3 enumeration: for all triples (a,b,c) distinct
    # if (a,b) and (b,c) edges but (a,c) not edge => add (a->b) <-> (c->b)
    for b in range(1, n+1):
        for a in range(1, n+1):
            if a==b or not adj[a][b]: continue
            for c in range(a+1, n+1):
                if c==b or not adj[b][c]: continue
                if adj[a][c]:  # triangle -> not induced P3
                    continue
                p = lit_orient(a,b)
                q = lit_orient(c,b)
                # equivalence => (¬p ∨ q) and (¬q ∨ p)
                ts.add_clause(-p, q)
                ts.add_clause(-q, p)

    ok = ts.solve()
    return ok, ts.clauses*2  # (roughly) count “implication arcs”, not critical

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", required=True)
    args = ap.parse_args()

    n, edges = read_edge_list(args.graph)

    t0 = time.perf_counter()
    ok, _ = naive_o_n3_builder(n, edges)
    dt = time.perf_counter() - t0

    print(f"NAIVE O(n^3) result: {ok}")
    print(f"n={n} m={len(edges)} time_sec={dt:.4f}")

if __name__ == "__main__":
    main()
