# Agent Design Q&A — New 3-Agent Setup

**Context**: Supervisor meeting Mar 23 defined 3 agents (Naive, Deterministic, Stochastic) all re-planning on the same 6h cycle. Before implementing, these design questions need answers.

---

## Q1. What is a "leg" — spatial or temporal?

Current executor iterates spatially: one leg = one node-to-node segment (~1 nm for exp_b, ~5 nm for exp_d). At 12 kn, a 1 nm leg ≈ 5 min, a 5 nm leg ≈ 25 min. A single 6h forecast cycle spans ~72 spatial legs (exp_b) or ~14 spatial legs (exp_d).

When the supervisor says "plans against the same 6h cycle", does the agent:

- **(a)** Plan once every 6 hours of elapsed time, producing a speed schedule for all remaining spatial legs?
- **(b)** Plan once per spatial leg, but the weather snapshot only updates every 6h?

**Answer**: **(a)** — Plan once every 6h elapsed, produce speed schedule for all remaining spatial legs. Spatial legs are an execution detail, not a decision granularity.

---

## Q2. What does the Naive agent compute at re-plan?

"Averages the speed needed to complete the voyage under ETA."

- At re-plan, Naive computes `remaining_distance / remaining_time` → one constant SOG for everything ahead. No weather, no optimization. Clear enough.

But edge cases:

- If already behind schedule (remaining_time < remaining_distance / max_SOG), does Naive sail at max speed and accept late arrival? Or is it infeasible?
- Does Naive use λ (soft ETA penalty)? If yes, it needs an optimizer. If no, it just does arithmetic.
- Does Naive compute fuel at plan time? Or only the executor measures fuel after the fact?

**Answer**: No optimizer, no λ. Pure arithmetic: `SOG = remaining_distance / remaining_time`. If behind schedule (SOG > max), sail at max speed and arrive late. If ahead (SOG < min), sail at min speed. No fuel computation at plan time — only the executor measures fuel after the fact.

---

## Q3. What does "actual weather treated as constant" mean for the Deterministic agent?

At re-plan hour H, the Deterministic agent sees actual weather. Two interpretations:

- **(a) Per-segment actuals, frozen**: Take the actual weather observed at **each future segment's location** (from sample_hour H) and assume those values hold forever. Uses spatial weather variation but no temporal variation. Requires the ship to "know" weather at locations it hasn't reached — effectively a global observation network.

- **(b) Current-location weather, applied everywhere**: Take the weather **where the ship is right now** and apply it uniformly to all remaining segments. Single weather condition for the whole remaining voyage. More realistic (ship has local sensors only).

The supervisor said "takes the actual weather in every segment" — this points to **(a)**.

But if (a): the Deterministic agent is spatially omniscient. It knows today's weather at a point 3 days ahead on the route. Is that a reasonable assumption? (Satellite data, shore reports, routing services could provide this.)

**Answer**: **(a)** — Spatially omniscient. At re-plan hour H, agent sees actual weather at all waypoints (satellite data, routing services). Assumes these values hold for the entire remaining voyage. Weakness is temporal, not spatial — knows today perfectly, assumes tomorrow is the same.

---

## Q4. What optimizer does each agent use?

The new framing focuses on **information quality** (none / actual / forecast), not optimizer choice. But LP and DP produce different results:

- **LP**: Optimizes per-segment (6–10 coarse segments), averages weather within each
- **DP**: Optimizes per-node (138–391 fine nodes), finer spatial granularity

Options:

| Option | Setup | Pro | Con |
|--------|-------|-----|-----|
| **(a)** Same optimizer for all | All use DP (or all LP) | Clean comparison — isolates information variable | Loses LP vs DP comparison |
| **(b)** Different per agent | Naive=none, Det=LP, Stoch=DP | Matches "complexity ladder" | Confounds information with method |
| **(c)** Both | 3 agents × 2 optimizers = 6 configs | Complete picture | More experiments, harder to present |
| **(d)** Optimizer is irrelevant for Naive | Naive=arithmetic, Det+Stoch use same optimizer | Naive genuinely doesn't optimize | Still need to choose LP or DP for the other two |

**Answer**: **(d)** — Naive = arithmetic (no optimizer), Deterministic + Stochastic = same optimizer (DP). Isolates the information variable cleanly. DP chosen over LP because it operates per-node, handles time-varying weather natively, and avoids the spatial-averaging confound. LP can be a secondary experiment later.

---

## Q5. What happens at course changes / mid-leg re-plans?

Re-planning happens on a **time** schedule (every 6h), but course changes happen at **spatial** waypoints. A re-plan at hour 18 might land mid-leg between WP3 and WP4.

Options:

| Option | Description | Pro | Con |
|--------|-------------|-----|-----|
| **(a)** Re-plan from exact position | Interpolate a partial remaining leg, then full legs after | Most accurate | Complex — need to split legs, handle partial distances |
| **(b)** Re-plan from next waypoint | Ignore partial leg, re-plan from next WP onward | Simple, clean leg boundaries | Wastes the partial leg (small inaccuracy) |
| **(c)** Re-plan at leg boundaries only | Defer re-plan to the next leg completion after the 6h mark | Avoids mid-leg issues entirely | Re-plan timing drifts from exact 6h cycle |
| **(d)** Time-based legs | Redefine legs as 6h time blocks, not spatial segments | Aligns with forecast cycle | Loses waypoint/segment structure entirely |

Related: if the ship is mid-leg when re-plan triggers, does it finish the current leg at the old SOG before switching to the new plan?

**Answer**: **(c)** — Defer re-plan to the next leg completion after the 6h mark. When `cum_time >= next_replan_time` at end of a leg, trigger re-plan. Drift is negligible (~25 min max for 5nm legs, ~5 min for 1nm). Keeps clean leg boundaries — plan always starts at a waypoint. Ship finishes current leg at old SOG, then switches.

---

## Q6. How does the Stochastic agent handle "actual for current leg + forecast for future"?

"Actual weather for the first 6h decision leg, forecast for the rest."

The "current 6h leg" isn't a spatial leg — it's a **time window**. During 6h the ship crosses ~14 spatial legs (exp_d, 5nm) or ~72 spatial legs (exp_b, 1nm).

Sub-questions:

**(6a)** "Actual weather for 6h" means:
- (i) Use the **single observation at re-plan time** for all spatial legs in the next 6h window? (Frozen snapshot)
- (ii) Use **per-waypoint actual observations** from sample_hour H for the spatial legs in the 6h window? (Spatially varying but temporally frozen — same as Deterministic for those legs)

**(6b)** For the forecast portion beyond 6h:
- Which forecast? The one issued at the current NWP cycle (every 6h: 0, 6, 12, 18 UTC)?
- Forecast hours are indexed from issuance. At voyage hour 18, a fresh forecast gives forecast_hour=0 for "now", forecast_hour=6 for hour 24, etc. Does the Stochastic agent always use the **freshest available forecast**?

**(6c)** If both Deterministic and Stochastic use per-waypoint actuals for the current 6h window, then the **only** difference between them is what they assume for the **future**:
- Deterministic: future weather = today's actuals (frozen)
- Stochastic: future weather = forecast (degrades with lead time)

Is this the intended distinction?

**Answer**: **(6a)** Per-waypoint actuals at sample_hour H for the current 6h window — same as Deterministic. **(6b)** Freshest available forecast from current NWP cycle for all future legs. **(6c)** Yes — Deterministic and Stochastic are identical for the current 6h window. The only difference is beyond 6h: Deterministic freezes today's actuals, Stochastic uses forecast. Isolates exactly one variable: does forecast information help vs assuming persistence?

---

## Q7. What happens between re-plans?

Between two 6h re-plan points, the ship sails through many spatial legs. Two modes:

- **(a) Rigid schedule**: Ship follows the planned SOG at each leg, regardless of actual weather. If actual weather differs from plan, the ship arrives at different times than planned — but doesn't adjust until next re-plan. Flow classification still happens (executor clamps SWS to [min, max]) but no re-planning in between.

- **(b) Reactive execution**: Ship follows planned SOG but executor still runs leg-by-leg, and if Flow 2 occurs, some emergency response is triggered even between re-plan cycles.

Option (a) is cleaner for the new setup — all agents follow their plan for 6h, then re-plan. The executor still clamps SWS (a ship physically can't exceed max power), but the agent doesn't "know" about it until the next re-plan.

**Answer**: **(a)** — Rigid schedule + clamp. Ship follows planned SOG, executor clamps SWS to [min, max] physically, Flow classification recorded for analysis but no reactive response between re-plans. Agent only learns what happened at the next 6h re-plan point. All three agents equally blind between cycles.

---

## Q8. Does the HDF5 data support all three agents?

| Agent | Data needed | Available in HDF5? |
|-------|------------|-------------------|
| **Naive** | No weather | Yes (trivially) |
| **Deterministic** | Actual weather at all waypoints at re-plan time | Yes — `actual_weather` at `sample_hour = H` has all waypoints |
| **Stochastic** | Actual at current waypoints + forecast for future | Yes — `actual_weather` for current + `predicted_weather` grid for future |

One concern: the collector samples every 6h, aligned to NWP cycles. If the ship's 6h re-plan cycle drifts out of alignment with NWP cycles (due to speed variation), the agent might need weather at sample_hour=7 but only have 6 and 12.

- Force re-plan alignment to NWP hours (0, 6, 12, 18, ...)? Then re-plan interval isn't exactly 6h elapsed, but always on the data grid.
- Or interpolate between available sample hours?

**Answer**: **Force alignment to NWP hours** (0, 6, 12, 18h...). Data is on this grid — no interpolation needed. Realistic: real NWP forecasts are issued at fixed UTC times. First re-plan cycle may be shorter than 6h if departure is between cycles; every cycle after is exactly 6h.

---

## Summary: Critical Decisions

| # | Question | Options | Decision |
|---|----------|---------|----------|
| 1 | Re-plan trigger | (a) Every 6h elapsed / (b) Every spatial leg | **(a)** Every 6h elapsed |
| 2 | Naive edge cases | Uses λ? Accepts late arrival at max speed? | No λ, no optimizer. Max speed if behind, min if ahead |
| 3 | Deterministic weather scope | (a) All waypoints (omniscient) / (b) Local only | **(a)** All waypoints — omniscient spatially, frozen temporally |
| 4 | Optimizer choice | (a) Same for all / (b) Different / (c) Both / (d) Naive=none, rest=same | **(d)** Naive=arithmetic, Det+Stoch=DP |
| 5 | Mid-leg re-plan | (a) Exact position / (b) Next WP / (c) Defer to leg boundary / (d) Time-based legs | **(c)** Defer to leg boundary, negligible drift |
| 6 | Stochastic current-leg weather | (i) Single frozen obs / (ii) Per-waypoint actuals | **(ii)** Per-waypoint actuals (same as Det for current 6h) |
| 7 | Between re-plans | (a) Rigid schedule + clamp / (b) Reactive mid-cycle | **(a)** Rigid + clamp, no reactive mid-cycle |
| 8 | Re-plan ↔ NWP alignment | Force alignment / Allow drift + interpolate | **Force alignment** to NWP hours (0, 6, 12, 18...) |

---

*Created 2026-03-25. Fill answers before implementing.*
