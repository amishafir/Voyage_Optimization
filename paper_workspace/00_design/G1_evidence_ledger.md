# G1 — Evidence Ledger

**Gate status:** DRAFT (populate → review → freeze). Once frozen, every claim in G2 must
cite a row here; nothing in the paper may assert a number absent from this ledger.

**Scope (locked):** Primary = the two June chain sweeps (Mode C + RH), both routes.
Secondary = earlier forecast-error / horizon / replan / NWP analyses, *to vet*.
**Constraint:** no new runs — this is a closed audit of `../results/` + `../context/docs/`.

**Source-of-truth rule:** numbers come from the on-disk CSVs where present; otherwise from
the user-designated verified prep `context/docs/meeting_prep_2026_06_15.md` (RH) and
`meeting_prep_2026_06_01.md §5.5` (Mode C). The CSVs and these preps agree to 3 dp where
both exist (spot-checked).

**Credibility legend:**
`✅ VERIFIED` on-disk run output (+ verified prep) · `⚠️ SPARSE` exists but thin/coarse ·
`🔶 SECONDARY` earlier run / different (LP-DP-RH) framing, vet before use · `❌ ABSENT` needed but not in any output.

---

## A. PRIMARY — Mode C oracle: SR vs Luo on actual weather (perfect foresight ceiling)

Source: `results/2026_06_01_chain_sweep/results.csv` (19 rows, Python). Mirrors `meeting_prep_2026_06_01.md §5.5`. **Negative gap = SR burns less fuel.** All voyages: slack = 0 (arrive exactly at ETA). `✅ VERIFIED`

### A.1 Route 1 — Malacca (ETA 280 h, L = 3393.2 nm), n = 7
| voyage | sh_base | SR (mt) | Luo (mt) | gap (mt) | gap % |
|---:|---:|---:|---:|---:|---:|
| 0 | 6 | 354.821 | 361.561 | −6.740 | −1.86 |
| 1 | 286 | 355.225 | 364.675 | −9.450 | −2.59 |
| 2 | 566 | 337.702 | 342.414 | −4.713 | −1.38 |
| 3 | 846 | 348.191 | 353.146 | −4.955 | −1.40 |
| 4 | 1126 | 337.604 | 340.874 | −3.270 | −0.96 |
| 5 | 1406 | 334.828 | 343.857 | −9.029 | −2.63 |
| 6 | 1686 | 345.728 | 352.312 | −6.584 | −1.87 |

### A.2 Route 2 — Atlantic (ETA 168 h, L = 1954.7 nm), n = 12
| voyage | sh_base | SR (mt) | Luo (mt) | gap (mt) | gap % |
|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 203.198 | 210.250 | −7.052 | −3.35 |
| 1 | 168 | 204.167 | 209.507 | −5.340 | −2.55 |
| 2 | 336 | 195.239 | 201.952 | −6.713 | −3.32 |
| 3 | 504 | 206.124 | 212.224 | −6.100 | −2.87 |
| 4 | 672 | 215.931 | 223.495 | −7.565 | −3.38 |
| 5 | 840 | 190.752 | 196.894 | −6.142 | −3.12 |
| 6 | 1008 | 227.914 | 233.853 | −5.939 | −2.54 |
| 7 | 1176 | 194.397 | 198.253 | −3.856 | −1.94 |
| 8 | 1344 | 194.641 | 197.054 | −2.413 | −1.22 |
| 9 | 1512 | 192.750 | 196.896 | −4.146 | −2.11 |
| 10 | 1680 | 199.101 | 203.488 | −4.387 | −2.16 |
| 11 | 1848 | 198.568 | 204.405 | −5.837 | −2.86 |

### A.3 Mode-C aggregates `✅ VERIFIED`
| Route | n | SR mean±std (mt) | Luo mean±std (mt) | gap mean (mt) | gap % mean | SR fuel range (spread) | gap range (mt) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 7 | 344.87 ± 7.77 | 351.26 ± 8.72 | **−6.39** | **−1.81 %** | 334.8–355.2 (20.4) | −3.27 … −9.45 |
| 2 | 12 | 201.90 ± 10.32 | 207.36 ± 11.03 | **−5.46** | **−2.62 %** | 190.8–227.9 (37.1) | −2.41 … −7.57 |

**Key Mode-C facts:** SR < Luo on **19/19** voyages. Absolute gap comparable across routes
(~5–6 mt) but ~1.4× larger in % on the shorter Atlantic. Atlantic fuel spread ~3× Route 1
per voyage-hour (weather sensitivity). One bad window (R2 sh=1008, 227.9 mt) costs more than
the entire SR−Luo gap.

---

## B. PRIMARY — Rolling Horizon: RH-SR / RH-Luo vs Naive (operational floor)

Mixed nowcast/forecast plan, execute block-0 only, re-plan every 6 h. Headline = vs **Naive**
(fixed mean-SOG). Reference = vs **Mode C oracle** (cannot be beaten). C++ chain.
Source: `meeting_prep_2026_06_15.md §6.2/§6.3` + `results/2026_06_15_rh_cpp_chain/results.csv`.
**Negative % = RH saves vs Naive.** `✅ VERIFIED`

### B.1 Route 2 — Atlantic (ETA 168), n = 12 (prep §6.2; route2 not in aggregated CSV — see §F)
| sh_base | oracle SR | Naive | RH-SR | RH-Luo | RH-SR vs Naive | RH-Luo vs Naive |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 203.357 | 212.609 | 205.001 | 212.115 | −3.58 % | −0.23 % |
| 168 | — | 212.775 | 208.340 | 211.409 | −2.08 % | −0.64 % |
| 336 | — | 203.647 | 200.985 | 203.417 | −1.31 % | −0.11 % |
| 504 | — | 214.538 | 212.606 | 216.006 | −0.90 % | **+0.68 %** |
| 672 | — | 225.978 | 222.380 | 224.904 | −1.59 % | −0.48 % |
| 840 | — | 200.496 | 192.982 | 199.037 | **−3.75 %** | −0.73 % |
| 1008 | — | 237.087 | 230.532 | 235.327 | −2.76 % | −0.74 % |
| 1176 | — | 200.425 | 197.329 | 200.708 | −1.54 % | **+0.14 %** |
| 1344 | — | 199.348 | 200.816 | 200.486 | **+0.74 %** | **+0.57 %** |
| 1512 | — | 198.987 | 195.577 | 198.280 | −1.71 % | −0.36 % |
| 1680 | — | 206.864 | 201.651 | 205.700 | −2.52 % | −0.56 % |
| 1848 | — | 206.103 | 201.912 | 206.271 | −2.03 % | **+0.08 %** |
| **mean** | | | | | **−1.92 %** | **−0.20 %** |

### B.2 Route 1 — Malacca (ETA 280, 47 re-plans, partial 4 h final block), n = 7
Source: `results/2026_06_15_rh_cpp_chain/results.csv` (route1 rows present) + prep §6.3.
| sh_base | oracle SR | Naive | RH-SR | RH-Luo | RH-SR vs Naive | RH-Luo vs Naive | RH-SR vs oracle (mt) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 6 | 354.914 | 362.743 | 358.859 | 362.565 | −1.07 % | −0.05 % | 3.94 |
| 286 | 355.228 | 367.034 | 358.726 | 367.719 | −2.26 % | **+0.19 %** | 3.50 |
| 566 | 338.250 | 345.423 | 342.820 | 344.514 | −0.75 % | −0.26 % | 4.57 |
| 846 | 348.528 | 354.735 | 350.330 | 354.358 | −1.24 % | −0.11 % | 1.80 |
| 1126 | 337.606 | 342.677 | 341.550 | 341.694 | −0.33 % | −0.29 % | 3.94 |
| 1406 | 335.233 | 346.186 | 344.111 | 346.573 | −0.60 % | **+0.11 %** | 8.88 |
| 1686 | 347.230 | 356.032 | 349.321 | 355.097 | −1.88 % | −0.26 % | 2.09 |
| **mean** | | | | | **−1.16 %** | **−0.10 %** | ~4.1 |

### B.3 RH single-voyage Python validation (Route 2, sh_base=0) `✅ VERIFIED` (prep §4.11)
Naive 212.467 · RH-SR **204.851 (−3.58 %)** · RH-Luo **212.439 (−0.01 %)**. RH-SR +1.653 mt
over oracle (203.198); RH-Luo +2.189 over oracle (210.250). C++ reproduces within ~0.15 %.
Divergence diagnostic: RH-SR changed block-0 SOG on 8/27 re-plans (30 %, mean |Δ| 0.19 kn);
RH-Luo 17/27 (63 %, mean |Δ| 0.43 kn) — "Luo fidgets more, gains less."

### B.4 RH aggregates `✅ VERIFIED`
- **RH-SR saves on 18/19 voyages** (mean −1.92 % R2, −1.16 % R1; best −3.75 %; single loss R2 sh=1344 +0.74 %).
- **RH-Luo ≈ break-even** (mean −0.20 % R2, −0.10 % R1; marginally positive on 6/19).
- RH-SR sits **above oracle by ~1.8–8.9 mt** (cost of imperfect foresight). All voyages: reached ✓, slack 0 ✓, RH ≥ oracle ✓.

### B.5 Gate finding read from the CSV (discrepancy vs prose — see §F-2)
`luo_gates_ok = False` on Route 1 voyages **sh=286 and sh=1406** — the only two where
RH-Luo > Naive (+0.19 %, +0.11 %). The failing gate is "RH ≤ Naive," not reached/slack/oracle.
Consistent with the Jensen departure-dependence (B/C below), but the prep §6.3 prose says
"all 7 mechanically sound," which is true only for the reached/slack/oracle gates.

---

## C. CLAIM-READY DERIVED FACTS (what feeds G2)

| # | Fact | Evidence | Cred |
|---|------|----------|:--:|
| C-1 | SR beats Luo on fuel under perfect foresight, every voyage (19/19): ~6.4 mt / 1.8 % (R1), ~5.5 mt / 2.6 % (R2). | A.1–A.3 | ✅ |
| C-2 | The SR−Luo gap is comparable in absolute mt across routes but ~1.4× larger in % on the shorter voyage. | A.3 | ✅ |
| C-3 | Under realistic RH, RH-SR saves vs set-and-forget Naive on 18/19 (mean −1.9 % R2, −1.2 % R1); RH-Luo merely breaks even (≈ −0.2 % / −0.1 %). | B.1–B.4 | ✅ |
| C-4 | The SR-vs-Luo contrast is route-independent and stable across the full ~80-day collection window, in **both** Mode C and RH. | A + B | ✅ |
| C-5 | RH's benefit over Naive is **departure- and route-dependent**, bounded by weather variability via the Jensen tradeoff (constant speed is fuel-optimal on uniform weather; RH wins only when weather-routing gain > Jensen penalty of forecast-driven speed variation). RH-SR loses to Naive once (R2 sh=1344). | B.1, B.5, prep §6.2 | ✅ |
| C-6 | RH realised fuel sits in the `oracle ≤ RH ≤ Naive` sandwich; the oracle−RH gap is the cost of deciding under imperfect foresight (not a within-block sim gap — block-0 is planned on actual weather). | B.3, B.4, prep §4.10 | ✅ |
| C-7 | **Mechanism (the engine):** the SR advantage = exploiting within-block weather variation at H-line crossings, which Luo's per-block SOG-lock structurally cannot. Jensen's inequality on the convex (cubic) FCR. | prep §6.2/§6.4 + physics | ✅ (claim) / mechanism is analytic |

---

## D. COMPUTE / COMPLEXITY EVIDENCE — ⚠️ SPARSE (read before designing the 2nd axis)

**This is the weak part of the ledger and the user should see it plainly.** The fuel story is
airtight; the compute-tradeoff axis is thinly evidenced and will lean on *analytical*
complexity, not rich measured data.

| # | Item | Value | Source | Cred |
|---|------|-------|--------|:--:|
| D-1 | Mode-C chain compute columns (`sr_n_nodes/edges/build_s/solve_s`, `luo_n_blocks/solve_s`) | **all empty** in all 19 rows | `2026_06_01_chain_sweep/results.csv` | ❌ |
| D-2 | SR atomic-graph size, Route 1 | 152,571 nodes · 9,214,780 edges · 47 V-lines · 163 H-lines · SOG grid 61 | prep `06_01 §5.1` (parity run) | ⚠️ |
| D-3 | SR atomic-graph size, Route 2 | 71,861 nodes · 4,325,288 edges · 28 V-lines · 121 H-lines · SOG grid 61 | prep `06_01 §5.1` | ⚠️ |
| D-4 | Luo block count / lattice size | **not measured anywhere** — analytically ≈ T_steps (ETA/dt) × distance idx | (derive) | ❌→analytic |
| D-5 | Mode-C wall times (coarse, SR+Luo conflated) | total 130 min; R1 ~45, R2 ~85; ~3 min/voyage; 2 slow Luo ~21 min | prep `06_01 §5.5.3` | ⚠️ |
| D-6 | RH runtime, C++ vs Python | C++ ~2.0 min/voyage vs Python ~532 min (single voyage 8.9 h) | prep `06_15 §6.2, §4.12` | ⚠️ |
| D-7 | RH per-voyage runtime (C++) | populated for only 3 of 7 R1 voyages (8.9 / 9.2 / 10.8 min); rest `nan` | `2026_06_15_rh_cpp_chain/results.csv` | ⚠️ |
| D-8 | RH runtime budget table | **estimates, not measurements** — do NOT cite as measured | prep `06_15 §4.5` | ❌ |

**Implication for G2:** a *measured* fuel×compute Pareto is **not** supported by existing data.
What is supportable: (a) **analytical** graph-complexity comparison (atomic-edge O(V·H·K) vs
Luo block O(T·D)) using D-2/D-3 + a derived Luo size; (b) the **structural** argument that
Luo's per-block lock yields far fewer decision variables; (c) coarse, clearly-caveated
illustrative timings (D-5/D-6). The honest compute claim is *structural*, not benchmarked.

> **DECISION (2026-06-08, frozen):** Compute axis = **structural/analytical only.** One
> formulation-size table (atomic-edge vs block lattice) + the *freedom-cost* framing (the
> per-leg freedom that enlarges SR's graph is the same freedom that captures the fuel).
> **No** measured runtime claims, **no** fuel-vs-seconds Pareto. D-5/D-6 timings may appear
> once, clearly caveated as illustrative. Counts (D-2/D-3) are machine-independent and OK.

---

## E. SECONDARY — supporting analyses (earlier runs; 🔶 VET before use)

These predate the SR/Luo spine (they were computed under LP/DP/RH on exp_b / full-route,
Feb–Mar). In scope as "supporting" but each needs a relevance check before it can attach to
an SR/Luo claim. Numbers live in `context/docs/thesis_brainstorm.md`; not regenerated here.

> **DECISION (2026-06-08, frozen):** IN as supporting = **E-1, E-2, E-4, E-5** (the cluster
> that justifies the RH operational design — forecast error explains the oracle−RH gap; the
> 6 h / GFS-cycle pair justifies the re-plan cadence). OUT = **E-3, E-6** (LP/DP route-length
> and decomposition artifacts with no SR/Luo home; both routes fit within the horizon anyway).
> *Open to override on E-3 (horizon) if a route-length angle is wanted.*

| # | Analysis | Headline number | Source (thesis_brainstorm) | Decision |
|---|----------|-----------------|------|:--:|
| E-1 | Forecast error vs lead time (exp_b ground truth) | wind RMSE 4.13→8.40 km/h over 0–133 h (doubles); +bias to ~2.7 km/h | §6 | ✅ IN (supporting) |
| E-2 | Forecast error (Route 2) | wind RMSE +286 % over 144 h | §13 (Mar 15) | ✅ IN (supporting) |
| E-3 | Horizon sweep route-length dependence | flat from 24 h (short route); plateau at 72 h (long) | §5 | ❌ OUT (override possible) |
| E-4 | Replan frequency sweep | 1 h vs 6 h ≈ 0.12 %; 6 h optimal | §5 | ✅ IN (supporting) |
| E-5 | NWP model cycle | GFS 6 h / MFWAM 12 h / SMOC 24 h; 86 % hourly calls redundant | §6b | ✅ IN (supporting) |
| E-6 | 2×2 factorial decomposition | temporal +3.02 > spatial +2.44 kg, interaction −1.43 | §4 | ❌ OUT (LP/DP artifact) |

---

## F. PROVENANCE NOTES & DISCREPANCIES FOUND (read-through of raw data)

1. **Aggregated RH CSV holds Route 1 only.** `2026_06_15_rh_cpp_chain/results.csv` = header +
   7 Route-1 rows. The 12 Route-2 RH rows (§B.1) are *not* in the aggregated CSV — they come
   from the verified prep §6.2 (sourced from `route2/voyage_*/summary.json`). For full
   reproducibility, Route-2 RH should be re-aggregated, or the prep table cited as authority.
2. **Gate-flag vs prose mismatch (B.5).** CSV `luo_gates_ok = False` on R1 sh=286 & sh=1406;
   prep §6.3 says "all 7 mechanically sound." Both are right under different gate definitions
   (RH≤Naive vs reached/slack/oracle). State the precise gate when reporting.
3. **Two oracle sources differ by FP noise.** Mode-C chain (Python) R1 sh=6 SR = 354.821;
   RH chain (C++) embeds oracle SR = 354.914 (Δ ~0.03 %). Consistent with the ≤0.08 % C++↔Py
   parity floor. Pick one source per table; don't mix within a number.
4. **Mode-C compute columns exist in the schema but were never populated** (D-1). The compute
   axis cannot be sourced from the chain run itself.

---

## Freeze checklist — ✅ FROZEN 2026-06-08
- [x] A/B per-voyage tables spot-checked against CSVs — done for Mode C (A) and R1 RH (B.2); R2 RH (B.1) trusts prep §6.2 (see F-1).
- [x] C claim-ready facts each trace to an A/B/D/E row.
- [x] D compute caveats acknowledged — compute axis = **structural/analytical only** (§D decision).
- [x] E secondary items scoped — **E-1/E-2/E-4/E-5 in, E-3/E-6 out** (§E decision).
- [x] Sign off → **G2 open.**

**Carried into G2 as open items:** (1) re-aggregate or cite-as-authority R2 RH numbers (F-1);
(2) state precise gate when reporting RH≤Naive (F-2); (3) one oracle source per table (F-3).
