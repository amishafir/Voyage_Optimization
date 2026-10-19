# Tracing routes along AIS traffic lanes

How `config/routes/tacoma_anchorage.yaml`, `rotterdam_algeciras.yaml`, `kaohsiung_yokohama.yaml`,
`durban_cape_town.yaml` and `sydney_auckland.yaml` (Routes 3-7) were made on 2026-10-19.

## Data (not in the repository)

- **AIS density**: World Bank / IMF *Global Shipping Traffic Density*, layer "Ship Density -
  Commercial" (`shipdensity_commercial_.zip`, 458 MB, from
  https://datacatalog.worldbank.org/search/dataset/0037580; CC BY 4.0). AIS positions of
  commercial ships (cargo, tankers, tugs, supply vessels and the like) from Jan 2015 to Feb 2021,
  counted per 0.005 deg cell; one 9.8 GB uncompressed, tiled int32 GeoTIFF
  (`ShipDensity_Commercial1.tif`). Reference: Cerdeiro, Komaromi, Liu and Saeed (2020), IMF
  working paper, World Seaborne Trade Monitoring System.
- **Coastline**: Natural Earth 1:10m `ne_10m_land` and `ne_10m_minor_islands`
  (https://naciscdn.org/naturalearth/10m/physical/).
- **Python packages**: shapely, pyshp, tifffile (plus numpy, scipy, Pillow, PyYAML). The scripts
  take a first argument PYLIB, a directory to put first on `sys.path` (where the packages were
  installed with `pip install --target`), or `-` to use the normal environment.

## Method

1. `ais_cutout.py`: read the window around a route from the GeoTIFF and sum it to 0.02 deg
   cells (about 1.2 NM).
2. `ais_route.py`: the cheapest 8-connected sea path between the ports (and any forced
   pass-through points). Cost per NM is `1 + beta * rel`, where `rel` is how far the cell's
   `log10(count + 1)` lies below the largest within 30 NM, in units of 2 orders of magnitude,
   clipped to [0, 1]. A local traffic ridge (a lane) has `rel = 0`. The local normalization
   removes the coverage bias of the raw counts: terrestrial receivers near the coast log far
   more messages than satellites offshore. For each stretch, `beta` is the largest value
   (bisection, at most 20) whose path is at most 5% longer than the shortest sea path, so the
   route follows the densest traffic a ship on this trade would plausibly use. Land cells
   (Natural Earth, cell centre) are impassable, and no diagonal step passes a land corner.
   `--offshore` makes cells within 20 NM of land count as off-lane on chosen stretches, except
   within 25 NM of their ends. The path is then thinned (Douglas-Peucker in Mercator, where rhumb
   lines are straight) into rhumb-line legs within 1.5 NM of it near land, up to 6 NM far
   offshore (distance to land / 4 in between), each leg at least 0.3 NM off land except the
   harbour approaches. It writes `OUT.json` (waypoints, traced path) and `OUT.png` (white =
   lane, red = route).
3. `make_route_yaml.py`: writes the route files from the `.json` results, with any manual
   corrections listed in it.
4. `landcheck.py`: checks every leg of a route file (after the collector's 2 NM port trims)
   against the coastline and reports the clearance. `sea_gaps.py` lists the sea intervals along
   a parallel or meridian, which helps place pass-through points in straits.
5. `collect/verify_grid_alignment.py --midpoints 0` then checks the wind and current values
   along every subsegment with the live API.

## Commands used

```bash
TIF=ShipDensity_Commercial1.tif; P=PYLIB; NE=ne_data
python3 -I ais_cutout.py $P $TIF gulf_of_alaska.npz 46.5 62.0 -154.5 -121.5 4
python3 -I ais_cutout.py $P $TIF channel_biscay.npz 35.3 52.6 -12.0 5.2 4
python3 -I ais_cutout.py $P $TIF kuroshio.npz       20.8 36.2 119.0 141.5 4
python3 -I ais_cutout.py $P $TIF agulhas.npz       -36.8 -28.3 16.0 33.0 4
python3 -I ais_cutout.py $P $TIF tasman.npz        -38.8 -31.8 150.0 176.5 4
python3 -I ais_route.py $P $NE gulf_of_alaska.npz r3 "47.290,-122.450" "61.235,-149.910" \
    --via "48.45,-124.90;59.05,-151.90" --offshore 1
python3 -I ais_route.py $P $NE channel_biscay.npz r4 "51.985,4.045" "36.127,-5.423"
python3 -I ais_route.py $P $NE kuroshio.npz r5 "22.552,120.305" "35.440,139.760" --via "21.75,120.85"
python3 -I ais_route.py $P $NE agulhas.npz r6 -- "-29.865,31.075" "-33.902,18.435"   # "--": negative latitudes
python3 -I ais_route.py $P $NE tasman.npz  r7 -- "-33.975,151.215" "-36.840,174.780"
cd pipeline && python3 tools/routes/make_route_yaml.py DIR_WITH_r3_r4_r5_json
```

Results (2026-10-19):

| Route | Shortest sea path | Traced (detour) | Waypoints | Route after 2 NM trims |
|---|---|---|---|---|
| 3 Tacoma - Anchorage | 1,589 NM | +3.2% | 27 (from Admiralty Inlet) | 1,414 NM |
| 4 Rotterdam - Algeciras | 1,419 NM | +4.7% | 23 | 1,400 NM |
| 5 Kaohsiung - Yokohama | 1,420 NM | +4.5% | 34 | 1,416 NM |
| 6 Durban - Cape Town | 829 NM | +3.7% | 23 | 806 NM |
| 7 Sydney (Port Botany) - Auckland | 1,292 NM | +1.7% | 19 | 1,285 NM |

Path lengths on the 0.02 deg grid include its staircase; the route legs are shorter. Forced
pass-through points: Route 3 the Strait of Juan de Fuca entrance and Kennedy Entrance, with the
offshore rule on the Gulf crossing (otherwise the path takes the coastal tug and barge lanes,
which the commercial layer includes); Route 5 south of Taiwan (otherwise it takes the Taiwan
Strait). Route 3 was traced from Tacoma but is planned from its traced waypoint in Admiralty
Inlet (off Port Townsend): the currents model (SMOC) has no data in Puget Sound, the first 46 NM
(Tal's choice, 2026-10-19; pilotage waters anyway). The 7 waypoints before it are dropped
(`make_route_yaml.py`, `first` = 7). Route 6 starts just outside the Durban harbour entrance (the
basin is not connected to the sea on the 0.02 deg grid). Route 7: three waypoints of the Auckland
approach moved about 1 NM east into the Rangitoto Channel, where the traced steps ran along the
North Shore coast; offshore traffic in the Tasman is sparse, so the route is close to the
shortest sea path (mean lane score 0.65).

Live check (2026-10-19, `collect/verify_grid_alignment.py --midpoints 0 --boundaries 50` and the
waves at every current cell): no NaN wind, currents or waves anywhere on the five routes. Points
served by the predicted grid point, wind / currents: Route 3 1,067 / 1,058 of 1,072, Route 4
884 / 885 of 885, Route 5 897 / 893 of 897, Route 6 549 / 549 of 549, Route 7 773 / 766 of 773; the rest are near land, where the API substitutes a
neighbouring sea point. Rule (Tal, 2026-10-19): do not bend a route for wave data, which the
fuel model does not use; if waves are needed where the wave model has none, take the nearest
wave sample.
