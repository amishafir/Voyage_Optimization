# G2 — Claims & Contributions

**Gate status:** DRAFT → review → freeze. Built on frozen `G1_evidence_ledger.md`.
**Rule:** every claim cites ≥1 G1 row. A claim with no ledger support is not made.
A strong G1 row with no claim is a missed contribution — flagged. Killed claims are
listed explicitly (§Killed) to show the scope was chosen, not overlooked.

**Spine restated:** Per-leg speed freedom (SR) beats per-block SOG-locking (Luo 2024) —
explained by Jensen's inequality on the convex FCR — at the Mode-C oracle ceiling and the
RH operational floor, at a characterized *structural* compute cost.

---

## Headline claims

### CLAIM 1 — Mechanism (the engine of the paper)
**Per-block SOG-locking pays a structural fuel penalty that per-leg freedom avoids: holding
one speed across a block that spans varying weather is sub-optimal by Jensen's inequality on
the convex (cubic) FCR.** SR captures this by choosing SOG independently at each H-line
crossing; Luo's block lock cannot.
- **Evidence:** G1 C-7 (mechanism, analytic) + the empirical gap it predicts (C-1, C-3).
- **Strength:** Strong. Mechanism is analytic (convexity is exact); empirically corroborated in *both* modes on *both* routes.
- **Scope limit:** The penalty's *size* depends on within-block weather variation — small when weather is uniform (ties to Claim 5).
- **What it is NOT:** not a claim that Luo is wrongly implemented — `luo_main` is a faithful block-DP (G1 provenance); the limitation is structural, not a bug.

### CLAIM 2 — Magnitude under perfect foresight (oracle ceiling)
**With perfect weather knowledge, SR uses less fuel than Luo on every one of 19 voyages:
~6.4 mt (1.8 %) mean on Route 1, ~5.5 mt (2.6 %) mean on Route 2.**
- **Evidence:** G1 A.1–A.3, C-1. (19/19 negative gap; CSV-verified.)
- **Strength:** Very strong — full enumeration, on-disk data, no simulation assumptions.
- **Scope limit:** Oracle = upper bound on the achievable gap; not operationally attainable.

### CLAIM 3 — Route-length scaling of the gap
**The SR−Luo gap is comparable in absolute fuel across routes (~5–6 mt) but ~1.4× larger as a
percentage on the shorter, harsher Atlantic voyage (2.6 % vs 1.8 %).**
- **Evidence:** G1 C-2, A.3.
- **Strength:** Strong (two routes). **Generalization caveat:** two routes ≠ a curve; state as a contrast, not a law.

### CLAIM 4 — The advantage survives realistic operation (operational floor)
**Under rolling-horizon planning with real, imperfect forecasts, the SR advantage persists:
RH-SR saves vs set-and-forget Naive on 18/19 voyages (mean −1.9 % R2, −1.2 % R1; best −3.75 %),
while RH-Luo merely breaks even (≈ −0.2 % / −0.1 %).** The SR-vs-Luo contrast is the robust
signal, stable across both routes and the full ~80-day collection window.
- **Evidence:** G1 B.1–B.4, C-3, C-4.
- **Strength:** Strong. This is the operationally credible result (no frozen-weather assumption).
- **Reporting note:** RH chain is C++; cite one oracle source per table (G1 F-3). R2 RH from prep §6.2 (G1 F-1).

### CLAIM 5 — Boundedness (DISCUSSION LIMITATION — not a headline claim)
> **DECISION (2026-06-08):** Demoted to a **Discussion limitation**, not a headline finding.
> Headline stays the clean RH savings (Claim 4); the reversals are reported honestly in
> §Discussion as a bound, not sold as a designed result.

**RH's benefit over naive set-and-forget is departure- and route-dependent, bounded by weather
variability through the *same* Jensen tradeoff: on near-uniform-weather departures a constant
speed is near-optimal and RH can even lose (RH-SR > Naive on 1/19; RH-Luo on 6/19).**
- **Evidence:** G1 C-5, B.1, B.5 (gate flags), prep §6.2.
- **Role:** Discussion-section limitation supporting Claim 4. Still shown as a savings-vs-departure (sh_base) curve.

### CLAIM 6 — Structural compute cost (FOLDED INTO C-I, not a standalone contribution)
> **DECISION (2026-06-08):** Compute is **part of the mechanism contribution (C-I)**, not its
> own headline. Same freedom-cost coin: per-leg freedom enlarges the graph *and* captures the fuel.

**SR's fuel gain comes from solving a structurally larger problem: per-leg freedom yields an
atomic-edge graph of O(V·H·K) (152,571 nodes / 9.2M edges on Route 1) versus Luo's block
lattice of O(blocks·K). The per-leg freedom that enlarges SR's graph is the same freedom that
captures the fuel — cost and benefit are two faces of one design choice.**
- **Evidence:** G1 D-2, D-3 (counts, machine-independent) + analytic asymptotics + Claim 1.
- **Strength:** Moderate — *structural* only. **Hard limit:** no measured runtime / no fuel-vs-seconds Pareto (G1 D-1 columns empty; D decision). Illustrative timings (C++ ~2 min vs Python ~532 min/voyage) may appear once, clearly caveated.

---

## Supporting findings (not headline contributions; used in Methods/Discussion to justify the RH design)

| # | Finding | Role | Evidence |
|---|---------|------|----------|
| S-1 | Forecast error grows with lead time (wind RMSE doubles over 133 h, R1; +286 % over 144 h, R2) | Explains why RH sits *above* the oracle (cost of imperfect foresight, Claim 4) | G1 E-1, E-2 |
| S-2 | 6 h re-plan cadence aligns to the GFS model cycle; 86 % of hourly calls are redundant | Justifies the RH re-plan interval choice (not a tuned hyperparameter) | G1 E-4, E-5 |

---

## Contribution mapping — 3 contributions (FROZEN 2026-06-08)

| Contribution | Claims | One-line |
|---|---|---|
| **C-I — Mechanism + structural cost** | 1, 6 | Per-block SOG-locking is fuel-suboptimal by Jensen on the convex FCR; per-leg freedom recovers the loss — and the *same* freedom that enlarges SR's graph (O(V·H·K) vs Luo's O(blocks·K)) is what captures the fuel. Cost and benefit are one coin. |
| **C-II — Quantification (oracle)** | 2, 3 | We quantify the SR−Luo gap against a faithful Luo 2024 baseline over 19 voyages / two regimes: ~6 mt, 19/19, %-larger on shorter routes. |
| **C-III — Operational validation** | 4 (5 = limitation) | The advantage survives rolling-horizon planning under real forecasts (RH-SR saves on 18/19, RH-Luo breaks even). Boundedness (Claim 5) reported as a Discussion limitation. |

*Single foil = Luo 2024. LP/DP ranking-reversal dropped entirely (see Killed list).*

---

## Killed / out-of-scope claims (deliberately not made)

| Killed claim | Why |
|---|---|
| "SR is X seconds faster/slower than Luo" / fuel-vs-runtime Pareto | Measured compute data absent (G1 D-1). Compute axis is structural only. |
| "RH beats set-and-forget universally" | False — reverses on uniform-weather departures (G1 C-5, B.5). Replaced by Claim 5. |
| Temporal>spatial 2×2 factorial decomposition | LP/DP-framing artifact, no SR/Luo home (G1 E-6 OUT). |
| Horizon route-length plateau (72 h) | LP/DP-RH artifact; both routes fit within horizon (G1 E-3 OUT; override possible). |
| LP-vs-DP ranking reversal under SOG-targeting (old C1) | Superseded — the paper's foil is Luo 2024, not internal LP/DP. Jensen survives as Claim 1. |
| Mode B "value of perfect information" | Mode B never run; out of scope by design decision (RH + Mode C only). |

---

## Missed-contribution check (strong G1 rows with no claim?)
- G1 A weather-sensitivity facts (Atlantic spread ~3× Route 1/voyage-hour) — folded into Claim 3 context, not its own claim. **OK.**
- G1 B divergence diagnostic (Luo fidgets 63 % vs SR 30 %) — supports Claim 1/5 as a mechanism illustration; could be a figure. **Hold for G4.**

## Freeze checklist — ✅ FROZEN 2026-06-08
- [x] Each claim 1–6 traces to a G1 row.
- [x] Contribution count = **3** (compute C-6 folded into C-I).
- [x] Claim 5 (boundedness) = **Discussion limitation**, not headline.
- [x] LP/DP ranking-reversal **dropped entirely**; single foil = Luo 2024.
- [x] Killed list agreed in full (nothing rescued).
- [x] Sign off → **G3 open.**
