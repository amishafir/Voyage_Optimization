# State-neighbours figure redesign

**Status:** implemented 2026-08-16; final `v_max` ratification remains open  
**Paper figure:** `fig:state-neighbours`  
**Current generators:** `paper_workspace/figures/plot_state_neighbours.py` and
`plot_state_neighbours_hline.py`

## 1. Design outcome

The two panels will use one shared real time–distance block, one shared renderer, and one fixed
export geometry. They will differ only in the position of the source state:

- panel (a): the source is on the block's left distance line and inside the time interval;
- panel (b): the source is on the block's top time line and inside the distance interval.

Everything else—canvas, axes, block boundaries, colors, marks, line styles, typography, margins,
coordinate limits, and export settings—will be identical.

The redesign also aligns the labels with the paper's current coordinate convention: state tuples
are written **`(t,d)`**, even though the visual axes remain horizontal `d` and vertical `t`.

## 2. Selected real block

Use Route 1, the Persian Gulf–Strait of Malacca route, with the first frozen voyage
(`sh_base=6`, ETA 280 h). The geometry comes from the production analytic rhumb-line/grid frame,
not from hand-picked illustration values.

| Quantity | Selected value | Provenance |
|---|---:|---|
| Route distance | 3,393.240 NM | `persian_gulf_malacca_paper.yaml` |
| Voyage | Route 1, voyage 0, `sh_base=6` | quick/full golden-set convention |
| Time block | `[120.0, 126.0] h` | 6 h block, well after the initial block |
| Left distance line | `1,963.886308 NM` | analytic crossing of longitude 78.5°E |
| Right distance line | `1,995.718977 NM` | analytic crossing of longitude 79.0°E |
| Block width | `31.832669 NM` | difference of the two H-lines |
| Route segment | waypoint segment 8 | interior Indian Ocean portion of Route 1 |
| Time grid | `τ = 0.1 h` | production/paper grid |
| Distance grid | `δ = 1.0 NM` | production/paper grid |

This block is approximately 58% along the route. It is neither the first distance block nor the
first time block.

### Reproducibility rule

The generator must not store only the four numbers above. It must identify the route, voyage, time
block, and the two 0.5° longitude crossings, then assert that the regenerated values agree with the
recorded values to `1e-6`. A deliberate `--frozen-values` fallback may be provided for building the
paper without loading the experiment data, because the selected geometry itself depends only on the
route waypoints.

## 3. Source states

Both source states lie in the same selected block and on the production grid.

### Panel (a): state on a distance line

```text
s_a = (t,d) = (123.0 h, 1,963.886308 NM)
```

- `d` is the block's left distance boundary.
- `t = 123.0 h = 126.0 - 30τ`, so it is a real H-line grid state inside the block.
- The next walls are `d = 1,995.718977 NM` and `t = 126.0 h`.

### Panel (b): state on a time line

```text
s_b = (t,d) = (120.0 h, 1,979.718977 NM)
```

- `t` is the block's top time boundary.
- `d = 1,995.718977 - 16δ`, so it is a real V-line grid state inside the block.
- The next walls are the same as in panel (a).

These choices preserve the conceptual contrast while allowing the complete block to remain fixed
between panels.

## 4. Candidate construction

The plotting code must compute candidates from Eq. (5); it must not contain manually authored
candidate lists. For source `(t,d)` and selected block end `(t_next,d_next)`:

```text
family 1: (t_next - nτ, d_next), subject to 0 ≤ (d_next-d)/(t'-t) ≤ v_max
family 2: (t_next, d_next - nδ), subject to 0 ≤ (d'-d)/(t_next-t) ≤ v_max
wait:     (t_next, d), emitted according to the approved waiting convention
```

The common corner `(t_next,d_next)` belongs to both families but is rendered once.

### `v_max` dependency

The meeting still needs to ratify the `v_max` convention. The generator therefore takes `v_max`
as one explicit parameter and recomputes the candidates. For design/preview only, use the current
Route 1 runner convention:

```text
v_max = L/T + 3 = 15.118714 kn
```

Under that provisional value:

| Panel | Distance-wall times | Time-wall distances | Unique candidates |
|---|---|---|---:|
| (a) | `125.2–126.0 h` by `0.1 h` | `1,964.718977–1,995.718977 NM` by `1 NM`, plus wait at `1,963.886308 NM` | 41 |
| (b) | `121.1–126.0 h` by `0.1 h` | `1,979.718977–1,995.718977 NM` by `1 NM` (the first is the wait node) | 66 |

The final assets must be regenerated after the meeting if a different `v_max` is selected.

## 5. Shared renderer

Replace the duplicated plotting logic with one generator:

```text
paper_workspace/figures/plot_state_neighbours_pair.py
```

Recommended structure:

```text
BlockSpec     route/voyage identity, d_left, d_right, t_top, t_bottom, τ, δ, v_max
PanelSpec     panel id, source_t, source_d, source_line_type
candidates()  one Eq.-(5) implementation used by both panels
render()      one drawing function used by both panels
verify()      geometry, candidate, style, and export checks
```

The old scripts should become tiny compatibility wrappers or be removed after all callers use the
shared generator. There must be only one palette and only one implementation of each mark type.

## 6. Fixed panel geometry

Use fixed placement; do not use `tight_layout()`, `constrained_layout`, or `bbox_inches="tight"`,
because those make the exported page box depend on label content.

| Property | Fixed value |
|---|---|
| Figure size | `6.0 × 4.6 in` per panel |
| PNG resolution | `300 dpi` → exactly `1800 × 1380 px` |
| Main axes rectangle | `[0.12, 0.12, 0.72, 0.68]` in figure coordinates |
| Compass rectangle | `[0.06, 0.87, 0.34, 0.11]` |
| X limits | `[1,958.0, 2,002.0] NM` in both panels |
| Y limits | `[119.2, 126.8] h`, displayed in reverse order, in both panels |
| Save settings | fixed page box; no automatic crop or padding |

If label QA shows that these limits need adjustment, change them once in `BlockSpec` and apply the
same change to both panels.

The preferred paper asset is also a combined `state_neighbours_pair.pdf` generated in the same run.
Keeping one combined asset eliminates any residual alignment differences introduced by two LaTeX
minipages. The two individual PDFs/PNGs remain as QA outputs.

## 7. Shared visual language

| Object | Encoding in both panels |
|---|---|
| Active block | `#F4F7FA` fill |
| Distance boundaries | navy `#0D3B66`, solid |
| Time boundaries | slate `#6B7C8F`, dashed `(4,3)` |
| Speed cone fill | pale orange `#FFF3E0`, 0.85 opacity |
| `v_max` edge | orange `#E64A19`, 2.0 pt solid |
| `v=0` / wait edge | orange `#E64A19`, 2.0 pt solid |
| Source state | red `#C62828` circle, white edge |
| Distance-wall candidates | blue `#1565C0` circles |
| Time-wall candidates | green `#2E7D32` squares |
| Candidate fan: family 1 | muted blue `#8EA8C3`, 0.9 pt |
| Candidate fan: family 2 | muted green `#9DBF9E`, 0.9 pt |
| Inactive grid marks | `#CFD8DC` |
| Orientation compass | `#33475B` |

Marker sizes, white-edge widths, font sizes, label offsets, and z-order values must also be shared
constants. The only conditional styling is emphasis of the line that contains the source state:
the left distance boundary in panel (a), and the top time boundary in panel (b).

## 8. Label policy

The current scripts label every candidate, which is not readable with the real `τ=0.1 h` and
`δ=1 NM` grids. The redesigned figure will show every candidate marker but label a deterministic
subset.

Always label:

- all four block boundaries with both symbol and actual value;
- the source state with its actual `(t,d)` values;
- `v_max` and `v=0`;
- the first and last candidate in each family.

Intermediate labels:

- distance-wall time family: label whole hours plus the earliest feasible time;
- time-wall distance family: label every fourth or fifth node, chosen by one shared thinning rule;
- include units on boundary/source labels, not on every candidate.

All candidate marks remain visible. Fan lines are thinned independently of markers: draw the two
envelope legs and evenly spaced interior examples, with no more than eight visible fan lines per
family. The caption must say that all marks are candidates while numeric labels and fan lines are
thinned for legibility.

## 9. Paper changes

1. Replace the two separate `\includegraphics` calls with the combined pair asset if accepted.
2. Remove “values illustrative” from the caption.
3. State the real block: Route 1, voyage 0, `d∈[1963.886,1995.719] NM`,
   `t∈[120,126] h`, `τ=0.1 h`, `δ=1 NM`.
4. Use `(t,d)` consistently in the caption and source-state labels.
5. State that all candidate markers are shown but some fan lines and numeric labels are omitted for
   legibility.
6. Insert the final approved `v_max` value or convention before publication.

## 10. Acceptance tests

### Data and mathematics

- The selected boundary values regenerate from the Route 1 waypoints within `1e-6`.
- Both sources satisfy the state-space grid definition and lie inside the selected interior block.
- Every candidate lies on exactly one next wall (or the shared corner), is grid anchored, and has
  implied speed in `[0,v_max]`.
- No candidate belongs to the first distance or first time block.
- The displayed candidate counts equal the computed set sizes.

### Geometry and style

- Both individual PNGs are exactly `1800 × 1380 px`.
- Both PDFs have the same media box.
- Main-axes and compass bounding boxes are identical.
- X/Y limits, transforms, palette, marker sizes, line widths, dash patterns, typography, and z-order
  constants are identical.
- An overlay of the two blank block frames aligns pixel-for-pixel.

### Paper QA

- The combined figure remains readable at the paper's final two-panel width.
- No label is clipped or overlaps another required label.
- The caption's numeric values match the generator's printed provenance summary.
- The PDF compiles without overfull boxes and the two panel plot regions align exactly.

## 11. Decisions still required at the meeting

1. Ratify the numeric/conventional definition of `v_max`.
2. Ratify the waiting convention; geometry supports either free waiting or priced station-keeping.
3. Accept using Route 1 voyage 0 and the selected interior block.
4. Accept the combined pair asset as the paper-facing output.

## 12. Implementation result

The design is implemented in `paper_workspace/figures/plot_state_neighbours_pair.py`. The two old
generators are compatibility entry points into that shared implementation, and the paper now uses
the combined `state_neighbours_pair.pdf` asset.

The implementation run verified:

- the selected distance boundaries regenerate from the Route 1 waypoints within `1e-6`;
- the provisional Eq. (5) candidate sets contain 41 and 66 unique states for panels (a) and (b);
- both individual PNGs are exactly `1800 × 1380 px`, and their corresponding halves in the
  `3600 × 1380 px` combined PNG are pixel-identical;
- both individual PDF media boxes are exactly `432 × 331.2 pt`, and the combined PDF is exactly
  `864 × 331.2 pt`;
- required labels are visible and the two plot regions align exactly in the rendered output.

The paper itself was not compiled during this pass because no TeX engine is installed in the
workspace environment. Final regeneration is required only if the meeting selects a different
`v_max` or waiting convention.
