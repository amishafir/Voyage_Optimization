"""Write config/routes/<key>.yaml for Routes 3-7 from ais_route.py results (TRACE_DIR/r3.json, ...).

    cd pipeline && python3 tools/routes/make_route_yaml.py TRACE_DIR
"""
import json, math, sys

D = sys.argv[1]
METHOD = ("Traced on 2026-10-19 along the World Bank / IMF Global Shipping Traffic Density, commercial "
          "layer (AIS positions Jan 2015 - Feb 2021, 0.005 deg; CC BY 4.0; Cerdeiro et al. 2020), summed "
          "to 0.02 deg cells: the cheapest sea path whose cost per NM is 1 on a local traffic ridge (log "
          "density within 2 orders of magnitude of the maximum within 30 NM) and up to 21 off it, with the "
          "weight chosen per stretch so the path is at most 5% longer than the shortest sea path; no "
          "diagonal steps past land corners. Land is Natural Earth 1:10m land and minor islands. The path "
          "was thinned to rhumb-line legs within 1.5 NM of it near land (up to 6 NM far offshore), each leg "
          "at least 0.3 NM off land except the harbour approaches (pipeline/tools/routes/README.md).")
ROUTES = [
    ("r3", "tacoma_anchorage", "Tacoma to Anchorage (Gulf of Alaska), planned from Admiralty Inlet",
     "Container and ro-ro route from Puget Sound across the Gulf of Alaska to Cook Inlet, planned "
     "from Admiralty Inlet (off Port Townsend), {L:,.0f} nm, ~{d:.1f} days at 12 kn. Gulf of Alaska "
     "winter storm track (Aleutian Low): frequent gales and high seas; strong tidal currents in Cook "
     "Inlet.",
     ("Admiralty Inlet (off Port Townsend)", "Anchorage"),
     {1: "Strait of Juan de Fuca entrance", 2: "Kennedy Entrance"},
     "Pass-through points (forced): Strait of Juan de Fuca entrance and Kennedy Entrance. On the Gulf "
     "crossing, cells within 20 NM of land count as off-lane (25 NM exempt around those points), which "
     "keeps the route on the offshore lane instead of the coastal tug and barge lanes. The route was "
     "traced from Tacoma (47.290, -122.450), but the voyage is planned from the traced waypoint in "
     "Admiralty Inlet where the currents model (SMOC) has data: it has none in Puget Sound (Tacoma "
     "to Admiralty Inlet, the first 46 NM; pilotage waters), Tal's choice, 2026-10-19.",
     {}, 7),
    ("r4", "rotterdam_algeciras", "Rotterdam to Algeciras (English Channel and Bay of Biscay)",
     "One of the busiest lanes in the world: Dover Strait, the Channel, off Ushant, across the Bay of "
     "Biscay and down the Iberian coast to Gibraltar, {L:,.0f} nm, ~{d:.1f} days at 12 kn. Winter Biscay "
     "gales and Atlantic swell; strong tidal currents in the Channel.",
     ("Rotterdam (Maasmond)", "Algeciras"), {}, "", {}, 0),
    ("r5", "kaohsiung_yokohama", "Kaohsiung to Yokohama (Ryukyu chain and Kuroshio)",
     "Around southern Taiwan, along the Ryukyu chain and the Pacific coast of Japan into Tokyo Bay, "
     "{L:,.0f} nm, ~{d:.1f} days at 12 kn. Kuroshio (one of the strongest ocean currents), winter "
     "north-east monsoon gales, and typhoons until about November.",
     ("Kaohsiung", "Yokohama"), {1: "South of Taiwan (Eluanbi)"},
     "Pass-through point (forced): south of Taiwan, so the route rounds Eluanbi instead of taking the "
     "Taiwan Strait.", {}, 0),
    ("r6", "durban_cape_town", "Durban to Cape Town (Agulhas Current)",
     "Coastal route around the southern tip of Africa, {L:,.0f} nm, ~{d:.1f} days at 12 kn. The "
     "Agulhas Current (up to 4 to 5 kn) runs along the shelf edge, and south-west gales against it "
     "raise notorious seas off the Wild Coast and the Agulhas Bank; then the Cape of Good Hope.",
     ("Durban (outside the harbour entrance)", "Cape Town (Table Bay)"), {},
     "Starts just outside the Durban harbour entrance (-29.865, 31.075): on the 0.02 deg grid the "
     "harbour basin is not connected to the sea.", {}, 0),
    ("r7", "sydney_auckland", "Sydney (Port Botany) to Auckland (Tasman Sea)",
     "Trans-Tasman route from Botany Bay around the northern tip of New Zealand and into the Hauraki "
     "Gulf, {L:,.0f} nm, ~{d:.1f} days at 12 kn. Tasman Sea fronts and lows all year; strongest in "
     "the southern winter.",
     ("Sydney (Port Botany)", "Auckland"), {}, "",
     {15: (-36.7874, 174.8350, "moved 1.0 NM east into the Rangitoto Channel: the traced steps ran along the North Shore coast"),
      16: (-36.8074, 174.8350, "moved 1.0 NM east, as the previous waypoint"),
      17: (-36.8350, 174.8350, "moved 1.1 NM south-east, south of North Head")}, 0),
]


def wrap(text, prefix, width=96):
    out, cur = [], ""
    for w in text.split():
        if cur and len(prefix) + len(cur) + len(w) + 1 > width:
            out.append(prefix + cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    out.append(prefix + cur)
    return out


for tag, key, name, desc, ends, vias, note, moves, first in ROUTES:
    j = json.load(open(f"{D}/{tag}.json"))
    wps = [[round(a, 4), round(b, 4)] for a, b in j["waypoints"]]
    for k, (la, lo, why) in moves.items():
        wps[k] = [la, lo]
    wps = wps[first:]                      # the planned voyage starts at traced waypoint `first`
    L = sum(math.hypot((b[0] - a[0]) * 60, (b[1] - a[1]) * 60 * math.cos(math.radians(0.5 * (a[0] + b[0]))))
            for a, b in zip(wps, wps[1:]))
    names = {0: ends[0], len(wps) - 1: ends[1]}
    for si, nm in vias.items():
        sla, slo = j["stops"][si]
        k = min(range(len(wps)), key=lambda q: (wps[q][0] - sla) ** 2 + ((wps[q][1] - slo) * math.cos(math.radians(sla))) ** 2)
        names[k] = nm
    lines = [f"name: {name}", "description: >"] + wrap(desc.format(L=L, d=L / 12 / 24), "  ")
    lines += wrap(METHOD, "# ") + (wrap(note, "# ") if note else []) + ["waypoints:"]
    n = 0
    for k, (la, lo) in enumerate(wps):
        if k not in names:
            n += 1
        nm = names.get(k, f"AIS lane {n:02d}")
        row = f'  - {{lat: {la:.4f}, lon: {lo:.4f}, name: "{nm}"}}'
        if k in moves:
            row += f"   # {moves[k][2]}"
        lines.append(row)
    open(f"config/routes/{key}.yaml", "w").write("\n".join(lines) + "\n")
    print(f"{key}: {len(wps)} waypoints, {L:.1f} NM")
