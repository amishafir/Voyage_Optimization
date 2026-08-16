"""Compatibility entry point for panel (b) of fig:state-neighbours.

The data, geometry, and visual style now live in
``plot_state_neighbours_pair.py`` so panels (a) and (b) cannot drift.
"""

from plot_state_neighbours_pair import generate_assets


if __name__ == "__main__":
    generate_assets(panels=("b",), combined=False)
