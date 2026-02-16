#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import deque, defaultdict
from dataclasses import dataclass
from typing import List, Tuple, Dict, Set, Optional, Iterable

# Optional visualization deps
try:
    import networkx as nx  # type: ignore
    import matplotlib.pyplot as plt  # type: ignore
    HAS_VIZ = True
except Exception:
    HAS_VIZ = False


# ============================================================
#  2-SAT core (linear in implication graph size)
# ============================================================

def lit_to_node(lit: int) -> int:
    """literal: ±k (k>=1) -> node id in [0..2n-1]"""
    v = abs(lit) - 1
    return (2 * v) ^ (1 if lit < 0 else 0)

def neg_node(node: int) -> int:
    return node ^ 1

def kosaraju_scc(g: List[List[int]]) -> Tuple[List[int], int]:
    """Iterative Kosaraju: O(V+E)"""
    n = len(g)
    gr = [[] for _ in range(n)]
    for u in range(n):
        for v in g[u]:
            gr[v].append(u)

    visited = [False] * n
    order: List[int] = []

    for s in range(n):
        if visited[s]:
            continue
        stack = [(s, 0)]
        visited[s] = True
        while stack:
            u, i = stack[-1]
            if i < len(g[u]):
                v = g[u][i]
                stack[-1] = (u, i + 1)
                if not visited[v]:
                    visited[v] = True
                    stack.append((v, 0))
            else:
                stack.pop()
                order.append(u)

    comp = [-1] * n
    cid = 0
    for s in reversed(order):
        if comp[s] != -1:
            continue
        q = [s]
        comp[s] = cid
        while q:
            u = q.pop()
            for v in gr[u]:
                if comp[v] == -1:
                    comp[v] = cid
                    q.append(v)
        cid += 1

    return comp, cid


@dataclass(frozen=True)
class Clause:
    a: int
    b: int


class TwoSAT:
    def __init__(self, n_vars: int):
        self.n = n_vars
        self.g: List[List[int]] = [[] for _ in range(2 * n_vars)]
        self.clauses: List[Clause] = []

    def add_clause(self, a: int, b: int) -> None:
        # (a ∨ b) == (¬a -> b) and (¬b -> a)
        self.clauses.append(Clause(a, b))
        ua = lit_to_node(a)
        ub = lit_to_node(b)
        self.g[neg_node(ua)].append(ub)
        self.g[neg_node(ub)].append(ua)

    def add_implication(self, p: int, q: int) -> None:
        """Add p -> q as clause (¬p ∨ q)."""
        self.add_clause(-p, q)

    def solve(self) -> Tuple[bool, Optional[List[bool]]]:
        comp, _ = kosaraju_scc(self.g)
        for i in range(self.n):
            if comp[2 * i] == comp[2 * i + 1]:
                return False, None
        assignment = [False] * self.n
        for i in range(self.n):
            assignment[i] = comp[2 * i] > comp[2 * i + 1]
        return True, assignment


# ============================================================
#  Input
# ============================================================

def read_edge_list_auto(path: str) -> Tuple[int, List[Tuple[int, int]], Optional[List[int]]]:
    """
    Reads:
      - static:  n m  then m lines: u v
      - temporal: n m then m lines: u v t
    Returns (n, edges_sorted(u<v), labels_or_None aligned with edges list)
    """
    raw: List[Tuple[int, int, Optional[int]]] = []
    with open(path, "r", encoding="utf-8") as f:
        header = ""
        while header.strip() == "" or header.strip().startswith("c"):
            header = f.readline()
            if not header:
                raise ValueError("Empty file.")
        n, m = map(int, header.split())

        for _ in range(m):
            line = f.readline()
            if not line:
                break
            line = line.strip()
            if not line or line.startswith("c"):
                continue
            parts = line.split()
            if len(parts) not in (2, 3):
                raise ValueError(f"Bad edge line: {line}")
            u = int(parts[0]); v = int(parts[1])
            if u == v:
                continue
            t = int(parts[2]) if len(parts) == 3 else None
            if u > v:
                u, v = v, u
            raw.append((u, v, t))

    # sort edges and keep labels aligned
    raw.sort(key=lambda x: (x[0], x[1], -1 if x[2] is None else x[2]))
    edges: List[Tuple[int, int]] = [(u, v) for (u, v, _) in raw]
    has_temporal = any(t is not None for (_, _, t) in raw)
    labels = [t if t is not None else 0 for (_, _, t) in raw] if has_temporal else None
    return n, edges, labels


# ============================================================
#  Degeneracy ordering
# ============================================================

def degeneracy_order(n: int, adj: List[List[int]]) -> Tuple[List[int], int]:
    deg = [0] * (n + 1)
    for v in range(1, n + 1):
        deg[v] = len(adj[v])

    maxdeg = max(deg[1:]) if n > 0 else 0
    buckets = [deque() for _ in range(maxdeg + 1)]
    for v in range(1, n + 1):
        buckets[deg[v]].append(v)

    cur_deg = deg[:]  # dynamic degree
    removed = [False] * (n + 1)

    order: List[int] = []
    k = 0
    cur = 0
    remaining = n

    while remaining > 0:
        while cur <= maxdeg and not buckets[cur]:
            cur += 1
        v = buckets[cur].popleft()
        if removed[v]:
            continue

        removed[v] = True
        remaining -= 1
        order.append(v)
        k = max(k, cur)

        for u in adj[v]:
            if removed[u]:
                continue
            du = cur_deg[u]
            if du <= 0:
                continue
            cur_deg[u] = du - 1
            buckets[du - 1].append(u)

    return order, k


# ============================================================
#  Static comparability (quasi-transitive) via induced P3 equivalences
# ============================================================

class StaticComparabilitySolver:
    """
    Variables: one per undirected edge (u<v)
      var(e)=True  means u->v
      var(e)=False means v->u

    Induced P3 constraint (a-b, b-c edges, but a-c missing):
      forbid a->b->c and forbid c->b->a
      Equivalent to: (a->b) <-> (c->b)
      Encode with 2 clauses: (¬p ∨ q) and (¬q ∨ p)
    """

    def __init__(self, n: int, edges: List[Tuple[int, int]]):
        self.n = n
        self.edges = edges

        self.adj_set: List[Set[int]] = [set() for _ in range(n + 1)]
        for u, v in edges:
            self.adj_set[u].add(v)
            self.adj_set[v].add(u)

        self.adj: List[List[int]] = [[] for _ in range(n + 1)]
        for v in range(1, n + 1):
            self.adj[v] = list(self.adj_set[v])

        self.edge_id: Dict[Tuple[int, int], int] = {}
        for idx, (u, v) in enumerate(edges, start=1):
            self.edge_id[(u, v)] = idx

        self.sat = TwoSAT(len(edges))
        self.clauses_added = 0

    def _var(self, u: int, v: int) -> int:
        if u < v:
            return self.edge_id[(u, v)]
        return self.edge_id[(v, u)]

    def lit_orient(self, u: int, v: int) -> int:
        """Literal meaning 'u -> v'."""
        var = self._var(u, v)
        return +var if u < v else -var

    def _add_equiv(self, p: int, q: int) -> None:
        self.sat.add_clause(-p, q)
        self.sat.add_clause(-q, p)
        self.clauses_added += 2

    def build_sparse_friendly(self, clause_cap: int) -> bool:
        mark = [0] * (self.n + 1)
        stamp = 1

        for b in range(1, self.n + 1):
            nbrs = self.adj[b]
            if len(nbrs) < 2:
                continue
            nbrs_sorted = sorted(nbrs)

            for i, a in enumerate(nbrs_sorted):
                stamp += 1
                if stamp == 1_000_000_000:
                    stamp = 1
                    mark[:] = [0] * (self.n + 1)

                for x in self.adj[a]:
                    mark[x] = stamp

                for c in nbrs_sorted[i + 1:]:
                    if mark[c] == stamp:
                        continue  # triangle -> not induced P3
                    p = self.lit_orient(a, b)
                    q = self.lit_orient(c, b)
                    self._add_equiv(p, q)
                    if self.clauses_added > clause_cap:
                        return False
        return True

    def build_bitset_fallback(self, clause_cap: int) -> None:
        N = [0] * (self.n + 1)
        for v in range(1, self.n + 1):
            bits = 0
            for u in self.adj[v]:
                bits |= (1 << u)
            N[v] = bits

        for b in range(1, self.n + 1):
            nb = N[b]
            if nb == 0:
                continue

            a_bits = nb
            while a_bits:
                lsb = a_bits & -a_bits
                a = (lsb.bit_length() - 1)
                a_bits -= lsb

                cand = nb & ~N[a]
                cand &= ~(1 << a)
                if a < self.n:
                    cand &= ~((1 << (a + 1)) - 1)  # keep only c > a

                while cand:
                    lsb2 = cand & -cand
                    c = (lsb2.bit_length() - 1)
                    cand -= lsb2

                    p = self.lit_orient(a, b)
                    q = self.lit_orient(c, b)
                    self._add_equiv(p, q)

                    if self.clauses_added > clause_cap:
                        raise RuntimeError(
                            f"Clause cap exceeded ({clause_cap}). Graph too dense for explicit 2-CNF in Python."
                        )

    def solve(self, k_threshold: int, clause_cap: int, force_fallback: bool = False
             ) -> Tuple[bool, Optional[Dict[Tuple[int, int], int]], Dict[str, int]]:
        stats: Dict[str, int] = {
            "mode": 0,
            "n": self.n,
            "m": len(self.edges),
            "degeneracy_k": -1,
            "clauses": 0,
            "used_fallback": 0,
        }

        _, k = degeneracy_order(self.n, self.adj)
        stats["degeneracy_k"] = k

        if force_fallback or (k > k_threshold):
            stats["used_fallback"] = 1
            self.build_bitset_fallback(clause_cap=clause_cap)
            stats["clauses"] = self.clauses_added
        else:
            ok_under_cap = self.build_sparse_friendly(clause_cap=clause_cap)
            stats["clauses"] = self.clauses_added
            if not ok_under_cap:
                stats["used_fallback"] = 1
                self.sat = TwoSAT(len(self.edges))
                self.clauses_added = 0
                self.build_bitset_fallback(clause_cap=clause_cap)
                stats["clauses"] = self.clauses_added

        ok, assign = self.sat.solve()
        if not ok:
            return False, None, stats

        assert assign is not None
        orient: Dict[Tuple[int, int], int] = {}
        for (u, v), idx in self.edge_id.items():
            orient[(u, v)] = +1 if assign[idx - 1] else -1
        return True, orient, stats


# ============================================================
#  Temporal reduction: build 2-CNF for Aug(G) forcing constraints
# ============================================================

class TemporalSolver:
    """
    Temporal graph G=(V,E,lambda). We build clauses for all forcing arcs in:
      - Imp(G): arcs based on 3-vertex paths / triangles (Definition 3)
      - Aug(G): adds extra arcs for correlated monolabel triangles (Definition 4)
    Each forcing arc (x->y) means: if arc x is chosen, arc y must be chosen,
    which becomes the 2-SAT clause (¬x ∨ y).
    """

    def __init__(self, n: int, edges: List[Tuple[int, int]], labels: List[int]):
        if labels is None:
            raise ValueError("TemporalSolver requires time labels (u v t lines).")
        self.n = n
        self.edges = edges
        self.labels = labels  # aligned with edges

        # edge time lookup
        self.time: Dict[Tuple[int, int], int] = {}
        for (u, v), t in zip(edges, labels):
            self.time[(u, v)] = t

        # adjacency with times
        self.adj: List[List[int]] = [[] for _ in range(n + 1)]
        for (u, v) in edges:
            self.adj[u].append(v)
            self.adj[v].append(u)

        # adjacency-by-label for triangle enumeration
        self.adj_by_label: List[Dict[int, Set[int]]] = [defaultdict(set) for _ in range(n + 1)]
        for (u, v), t in zip(edges, labels):
            self.adj_by_label[u][t].add(v)
            self.adj_by_label[v][t].add(u)

        # edge -> var id
        self.edge_id: Dict[Tuple[int, int], int] = {}
        for idx, (u, v) in enumerate(edges, start=1):
            self.edge_id[(u, v)] = idx

        self.sat = TwoSAT(len(edges))
        self.clauses_added = 0
        self.imp_arcs = 0
        self.aug_arcs = 0

    def has_edge(self, u: int, v: int) -> bool:
        if u > v:
            u, v = v, u
        return (u, v) in self.edge_id

    def edge_time(self, u: int, v: int) -> Optional[int]:
        if u > v:
            u, v = v, u
        return self.time.get((u, v))

    def _var(self, u: int, v: int) -> int:
        if u < v:
            return self.edge_id[(u, v)]
        return self.edge_id[(v, u)]

    def lit_orient(self, u: int, v: int) -> int:
        """Literal meaning 'u -> v'."""
        var = self._var(u, v)
        return +var if u < v else -var

    def _add_imp(self, x_u: int, x_v: int, y_u: int, y_v: int) -> None:
        """Add forcing (x_u,x_v) -> (y_u,y_v) i.e. clause (¬x ∨ y)."""
        x = self.lit_orient(x_u, x_v)
        y = self.lit_orient(y_u, y_v)
        self.sat.add_clause(-x, y)
        self.clauses_added += 1

    def build_imp(self, clause_cap: int) -> bool:
        """
        Definition 3:
        arcs (a,b)->(c,b) and (b,c)->(b,a) if:
          t(ab) <= t(bc) and (ac not edge OR t(ac) < t(bc)).
        """
        for b in range(1, self.n + 1):
            nb = self.adj[b]
            if len(nb) < 2:
                continue
            # ordered pairs (a,c)
            for a in nb:
                t_ab = self.edge_time(a, b)
                if t_ab is None:
                    continue
                for c in nb:
                    if c == a:
                        continue
                    t_bc = self.edge_time(b, c)
                    if t_bc is None:
                        continue
                    if t_ab > t_bc:
                        continue
                    t_ac = self.edge_time(a, c)
                    if (t_ac is None) or (t_ac < t_bc):
                        # (a,b)->(c,b)
                        self._add_imp(a, b, c, b)
                        self.imp_arcs += 1
                        # (b,c)->(b,a)
                        self._add_imp(b, c, b, a)
                        self.imp_arcs += 1
                        if self.clauses_added > clause_cap:
                            return False
        return True

    def _enumerate_monolabel_triangles(self) -> Iterable[Tuple[int, int, int, int]]:
        """
        Yields (u,v,w,t) with u<v<w and all three edges exist with label t.
        """
        for (u, v), t_uv in zip(self.edges, self.labels):
            # common neighbors w where uw and vw exist with same label t_uv
            Su = self.adj_by_label[u].get(t_uv, set())
            Sv = self.adj_by_label[v].get(t_uv, set())
            if not Su or not Sv:
                continue
            # intersect
            if len(Su) < len(Sv):
                common = [w for w in Su if w in Sv]
            else:
                common = [w for w in Sv if w in Su]
            for w in common:
                if w <= v:
                    continue
                yield (u, v, w, t_uv)

    def build_aug(self, clause_cap: int) -> bool:
        """
        Definition 4: for each correlated monolabel triangle (a,b,c,d),
        add arcs ((b,c)->(a,c)) and ((c,a)->(c,b)).

        Correlated monolabel triangle (a,b,c,d) requires:
          - abc monolabel label t
          - bd edge with time <= t
          - cd edge with time > t
          - if ad edge exists then time(ad) < t
        """
        for (x, y, z, t) in self._enumerate_monolabel_triangles():
            tri = (x, y, z)

            # try all ordered choices of (a,b,c) from the triangle
            for b, c, a in (
                (x, y, z), (y, x, z),
                (x, z, y), (z, x, y),
                (y, z, x), (z, y, x),
            ):
                # enumerate d via neighbors of b with bd<=t
                for d in self.adj[b]:
                    if d == a or d == b or d == c:
                        continue
                    t_bd = self.edge_time(b, d)
                    if t_bd is None or t_bd > t:
                        continue
                    t_cd = self.edge_time(c, d)
                    if t_cd is None or t_cd <= t:
                        continue
                    t_ad = self.edge_time(a, d)
                    if t_ad is not None and t_ad >= t:
                        continue

                    # Add arcs ((b,c)->(a,c)) and ((c,a)->(c,b))
                    self._add_imp(b, c, a, c)
                    self.aug_arcs += 1
                    self._add_imp(c, a, c, b)
                    self.aug_arcs += 1

                    if self.clauses_added > clause_cap:
                        return False
        return True

    def solve(self, clause_cap: int) -> Tuple[bool, Optional[Dict[Tuple[int, int], int]], Dict[str, int]]:
        """
        Builds Imp + Aug constraints, solves 2-SAT.
        Returns an orientation (assignment on edges). This corresponds to an ATTO-style closure constraint set.
        """
        stats: Dict[str, int] = {
            "mode": 1,
            "n": self.n,
            "m": len(self.edges),
            "clauses": 0,
            "imp_arcs": 0,
            "aug_arcs": 0,
            "hit_cap": 0,
        }

        ok1 = self.build_imp(clause_cap=clause_cap)
        ok2 = ok1 and self.build_aug(clause_cap=clause_cap)

        stats["clauses"] = self.clauses_added
        stats["imp_arcs"] = self.imp_arcs
        stats["aug_arcs"] = self.aug_arcs
        stats["hit_cap"] = 0 if (ok1 and ok2) else 1

        if not (ok1 and ok2):
            pass

        ok, assign = self.sat.solve()
        if not ok:
            return False, None, stats

        assert assign is not None
        orient: Dict[Tuple[int, int], int] = {}
        for (u, v), idx in self.edge_id.items():
            orient[(u, v)] = +1 if assign[idx - 1] else -1
        return True, orient, stats


# ============================================================
#  Output / viz
# ============================================================

def print_orientation(orient: Dict[Tuple[int, int], int]) -> None:
    for (u, v) in sorted(orient.keys()):
        if orient[(u, v)] == +1:
            print(f"{u} -> {v}")
        else:
            print(f"{v} -> {u}")

def _layout_pos(G: "nx.DiGraph", layout: str):
    if layout == "spring":
        return nx.spring_layout(G, seed=7)
    if layout == "kamada_kawai":
        return nx.kamada_kawai_layout(G)
    if layout == "circular":
        return nx.circular_layout(G)
    if layout == "shell":
        return nx.shell_layout(G)
    return nx.spring_layout(G, seed=7)

def save_png(
    n: int,
    undirected_edges: List[Tuple[int, int]],
    orient: Optional[Dict[Tuple[int, int], int]],
    out_png: str,
    layout: str = "spring",
    with_labels: bool = True,
) -> None:
    if not HAS_VIZ:
        raise RuntimeError("Visualization requires networkx + matplotlib. Install: pip install networkx matplotlib")

    if orient is None:
        G = nx.Graph()
        G.add_nodes_from(range(1, n + 1))
        G.add_edges_from(undirected_edges)
        pos = _layout_pos(nx.DiGraph(G), layout)
        plt.figure(figsize=(9, 7), dpi=200)
        nx.draw_networkx(G, pos=pos, with_labels=with_labels, node_size=800, arrows=False)
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(out_png)
        plt.close()
        return

    DG = nx.DiGraph()
    DG.add_nodes_from(range(1, n + 1))
    for (u, v), sgn in orient.items():
        if sgn == +1:
            DG.add_edge(u, v)
        else:
            DG.add_edge(v, u)

    pos = _layout_pos(DG, layout)
    plt.figure(figsize=(10, 8), dpi=220)
    nx.draw_networkx_nodes(DG, pos, node_size=900)
    if with_labels:
        nx.draw_networkx_labels(DG, pos)
    nx.draw_networkx_edges(DG, pos, arrows=True, arrowstyle="-|>", arrowsize=18, width=1.6)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()


# ============================================================
#  CLI
# ============================================================

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Static comparability (2-CNF + 2-SAT) and temporal (Imp/Aug -> 2-CNF + 2-SAT) with PNG export."
    )
    ap.add_argument("--graph", required=True, help="Edge-list file: 'n m' then m lines 'u v' OR 'u v t' (temporal).")
    ap.add_argument("--mode", choices=["auto", "static", "temporal"], default="auto",
                    help="auto: detect by presence of 3rd column. static: ignore labels. temporal: require labels.")
    ap.add_argument("--stats", action="store_true", help="Print stats.")

    # Static tuning
    ap.add_argument("--k-threshold", type=int, default=80, help="Static: if degeneracy k exceeds this, use fallback.")
    ap.add_argument("--clause-cap", type=int, default=2_000_000,
                    help="Max generated clauses before stopping/forcing fallback (default: 2,000,000).")
    ap.add_argument("--force-fallback", action="store_true", help="Static: always use bitset fallback.")

    # PNG export
    ap.add_argument("--png", default=None, help="If set, save a graph visualization to this PNG file.")
    ap.add_argument("--layout", default="spring",
                    choices=["spring", "kamada_kawai", "circular", "shell"],
                    help="Layout for PNG visualization.")
    ap.add_argument("--no-labels", action="store_true", help="Do not draw node labels on the PNG.")

    args = ap.parse_args()

    n, edges, labels = read_edge_list_auto(args.graph)

    # Decide mode
    if args.mode == "auto":
        mode = "temporal" if labels is not None else "static"
    else:
        mode = args.mode
    if mode == "temporal" and labels is None:
        raise SystemExit("Temporal mode requires edge lines 'u v t' (time label).")

    try:
        if mode == "static":
            solver = StaticComparabilitySolver(n, edges)
            ok, orient, stats = solver.solve(
                k_threshold=args.k_threshold,
                clause_cap=args.clause_cap,
                force_fallback=args.force_fallback,
            )
            print("SAT (quasi-transitive orientation exists):", ok)

        else:
            # temporal
            assert labels is not None
            tsolver = TemporalSolver(n, edges, labels)
            ok, orient, stats = tsolver.solve(clause_cap=args.clause_cap)
            print("SAT (temporal constraints via Imp/Aug are satisfiable):", ok)
            if stats.get("hit_cap", 0) == 1:
                print("WARNING: clause cap hit; formula may be incomplete. Increase --clause-cap for full test.")

    except RuntimeError as e:
        print("ERROR:", e)
        print("Tip: increase --clause-cap (more RAM/time) or test on smaller graphs.")
        return

    if args.stats:
        if mode == "static":
            print("mode = static")
            print("n =", stats["n"], "m =", stats["m"])
            print("degeneracy k =", stats["degeneracy_k"])
            print("generated clauses =", stats["clauses"])
            print("used fallback =", bool(stats["used_fallback"]))
        else:
            print("mode = temporal")
            print("n =", stats["n"], "m =", stats["m"])
            print("generated clauses =", stats["clauses"])
            print("Imp arcs (clauses) =", stats.get("imp_arcs", 0))
            print("Aug arcs (clauses) =", stats.get("aug_arcs", 0))

    if ok and orient is not None:
        print_orientation(orient)

    if args.png is not None:
        try:
            save_png(
                n=n,
                undirected_edges=edges,
                orient=orient if ok else None,
                out_png=args.png,
                layout=args.layout,
                with_labels=not args.no_labels,
            )
            print(f"[PNG saved] {args.png}")
        except Exception as e:
            print("PNG export failed:", e)
            if not HAS_VIZ:
                print("Install deps: pip install networkx matplotlib")


if __name__ == "__main__":
    main()
