# Meeting Prep — Supervisor Meeting, Mar 16 2026

---

## 1. Server & Collection Status

### What's running now (as of Mar 10)

| Server | Experiments | Current Hour | Samples (b / d) | Status |
|---|---|---|---|---|
| **Shlomo2** | Route 1, Route 2 | hour 48 | 8 / 9 | Leader, 1 timeout on Route 1 at hour 42 |
| **Edison** | Route 1, Route 2 | hour 30 | 6 / 6 | Backup, 1 timeout on Route 1 at hour 18 |
| **Shlomo1** | Route 1, Route 2 | hour 18 | 4 / 4 | Backup, clean (started Mar 9) |

All 3 servers collecting cleanly. exp_c permanently removed. Gaps on individual servers are covered by other servers — no data loss across the fleet.

### Data readiness

| Route | Best Server | Samples Done | Samples Needed | Est. Ready |
|---|---|---|---|---|
| **Route 1** (Persian Gulf–Indian Ocean, 131 wp) | Shlomo2 | 8 / 24 | 16 more | **~Mar 14** |
| **Route 2** (North Atlantic, 389 wp) | Shlomo2 | 9 / 28 | 19 more | **~Mar 15** |

### Old exp_b data (Shlomo1 pre-crash)

Downloaded to local: `pipeline/data/experiment_b_138wp_shlomo1_old.h5` — 171 samples, hours 0–225. This is the dataset used for Section 6 results. Available as fallback if new collection has issues.

---

## 2. Paper Progress

### Completed this week

- **Adversarial paper review** (paper-critic agent): found and fixed 8 issues
  - Jensen's inequality misattributed to Hvattum2013 (was their result, actually our interpretation)
  - "Bellman-Ford" → "dynamic programming" for Zaccone2018
  - Fake quotation marks on Psaraftis2023 paraphrase
  - "utmost dispatch" citation moved from Cariou2011 to Jia2017
  - Zis2020 standardization quote corrected to actual abstract wording
  - Yang2020/Tzortzis2021 no longer misclassified as "metaheuristic methods"
  - "approximately 3%" → "2.6%" per Bouman2017
  - "over 40 speed models" removed (vague count)

- **Sections 5–8 reorganized:**
  - §5.1 now leads with the real-time 6h collection+optimization pipeline as a major innovation
  - §7 fully written (Jensen mechanism, information hierarchy, weather tax, route-length dependence, 6h cycle as operational innovation, literature comparison, limitations)
  - §8 fully written (6 contributions, 4 recommendations, 5 future work items)

- **Naming convention updated:**
  - "Experiment B" → **Route 1** (Persian Gulf–Indian Ocean, mild)
  - "Experiment D" → **Route 2** (North Atlantic, harsh)
  - Applied across all .md sections and .tex

### Still TODO

- [ ] Write §6.5 (factorial decomposition) — needs the 2×2 table
- [ ] Write §6.6 (forecast error curves) — wind RMSE data
- [ ] Write §6.7 (re-planning frequency sweep)
- [ ] Write §6.8 (generalizability across routes) — needs Route 2 data
- [ ] Abstract (~250 words)
- [ ] Gap summary table (§2.6)
- [ ] Route 2 results throughout §6

---

## 3. Route 2 Data Plan

Once Shlomo2 reaches 28 samples (~Mar 15):
1. Download HDF5 from Shlomo2 (primary) and Edison/Shlomo1 (backup)
2. Merge best samples across servers to fill any gaps
3. Run LP/DP/RH pipeline on Route 2 data
4. Add Route 2 results to §6, update §6.8 generalizability table

---

## Questions for Discussion

1. **Route 2 results timeline**: Data ready ~Mar 15. Can we have Route 2 results in the paper by Mar 20?
2. **Pipeline as contribution**: Should the 6h collection+optimization infrastructure be a numbered contribution (C7), or keep it embedded in §5.1?
3. **Route 1-Coarse naming**: The factorial uses "Route 1-Coarse" (7 nodes) vs "Route 1" (138 nodes). Is this clear enough, or should we use "Route 1a/1b"?
4. **Third route**: Still needed? Or are 2 routes (2 ocean basins, mild vs harsh) sufficient?
