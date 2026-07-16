"""
DIAGNOSTIC — why is node-first ~1.5% worse than speed-first?

For a sample of reachable source nodes, compare the DISTINCT successor sets of
the two builders (speed-first `_emit_from_src` vs node-first `emit_nodefirst`),
and characterise the successors node-first MISSES (SOG, which boundary).
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from atomic_edges import _emit_from_src, build_atomic_edges  # noqa: E402
from frame import from_route as make_frame  # noqa: E402
from nodes import GraphConfig  # noqa: E402
from route import load_route_auto, synthesize_multi_window  # noqa: E402
from weather import VoyageWeather  # noqa: E402
from prototype_nodefirst import emit_nodefirst  # noqa: E402

YAML = "../config/routes/persian_gulf_malacca_paper.yaml"
H5 = "../data/experiment_d_391wp.h5"
SH = 0


def key(e):
    return (round(e.dst_t, 6), round(e.dst_d, 6))


def main():
    route, wps = load_route_auto(Path(YAML), eta_h=None)
    route = synthesize_multi_window(route, window_h=6.0)
    voyage = VoyageWeather(Path(H5))
    cfg = GraphConfig.from_route(route)
    cfg.zeta_nm, cfg.tau_h = 5.0, 0.5      # coarse = fast; gap is grid-independent
    mean = cfg.length_nm / cfg.eta_h
    cfg.v_min, cfg.v_max = mean - 3.0, mean + 3.0
    frame = make_frame(route, voyage, wps, cfg=cfg)
    print(f"grid zeta={cfg.zeta_nm} tau={cfg.tau_h} |V|={len(frame.sog_grid())} "
          f"v in [{cfg.v_min:.2f},{cfg.v_max:.2f}]")

    # reachable sources from the speed-first build
    nodes, _ = build_atomic_edges(frame, override_sample_hour=SH, verbose=False)
    srcs = [n for n in nodes if not n.is_sink]
    srcs = srcs[:: max(1, len(srcs) // 800)]   # sample ~800
    print(f"sampling {len(srcs)} source nodes\n")

    tot_sf = tot_nf = tot_sfonly = tot_nfonly = 0
    n_with_miss = 0
    miss_boundary = Counter()          # which line the missed successor sits on
    miss_sog_bins = Counter()          # SOG of missed successors, vs [v_min,v_max]
    examples = []

    for n in srcs:
        sf = {key(e): e for e in _emit_from_src(n.time_h, n.distance_nm, frame,
                                                override_sample_hour=SH)}
        nf = {key(e): e for e in emit_nodefirst(n.time_h, n.distance_nm, frame, SH)}
        sf_only = set(sf) - set(nf)
        nf_only = set(nf) - set(sf)
        tot_sf += len(sf); tot_nf += len(nf)
        tot_sfonly += len(sf_only); tot_nfonly += len(nf_only)
        if sf_only:
            n_with_miss += 1
        for k in sf_only:
            e = sf[k]
            on_dist = abs(e.dst_d - frame.next_h_distance(n.distance_nm)) < 1e-6 \
                if frame.next_h_distance(n.distance_nm) else False
            miss_boundary["distance-line" if on_dist else "time-line"] += 1
            if e.sog < cfg.v_min - 1e-6:
                miss_sog_bins["below v_min"] += 1
            elif e.sog > cfg.v_max + 1e-6:
                miss_sog_bins["above v_max"] += 1
            else:
                miss_sog_bins["inside [v_min,v_max]"] += 1
        if sf_only and len(examples) < 6:
            examples.append((n, sf, nf, sf_only))

    ns = len(srcs)
    print("=" * 60)
    print(f"avg distinct successors:  speed-first {tot_sf/ns:.1f}   node-first {tot_nf/ns:.1f}")
    print(f"avg speed-first-only (missed by node-first): {tot_sfonly/ns:.2f}")
    print(f"avg node-first-only (extra):                 {tot_nfonly/ns:.2f}")
    print(f"sources where node-first misses >=1:         {n_with_miss}/{ns}")
    print(f"\nmissed successors by boundary:  {dict(miss_boundary)}")
    print(f"missed successors by SOG:       {dict(miss_sog_bins)}")
    print("=" * 60)
    for n, sf, nf, sf_only in examples[:4]:
        print(f"\nsrc (t={n.time_h:.2f}, d={n.distance_nm:.2f})  "
              f"|sf|={len(sf)} |nf|={len(nf)}  next_d={frame.next_h_distance(n.distance_nm)} "
              f"next_t={frame.next_v_time(n.time_h)}")
        for k in sorted(sf_only)[:8]:
            e = sf[k]
            print(f"   MISSED dst(t={k[0]:.2f}, d={k[1]:.2f})  SOG={e.sog:.3f}")


if __name__ == "__main__":
    main()
