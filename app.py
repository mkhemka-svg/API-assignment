#!/usr/bin/env python3
"""Earthquake Explorer (USGS Earthquake Catalog API)

What this app does:
- Calls the USGS Earthquake Catalog API (event service) and requests results as GeoJSON.
- Lets you choose a time window (past N hours) and a minimum magnitude.
- Prints a ranked list of earthquakes (largest magnitude first).
- Optionally plots magnitude over time using matplotlib.

USGS event service documentation:
  https://earthquake.usgs.gov/fdsnws/event/1/

Example request shape (your code builds this URL with params):
  GET https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2026-02-06T12:00:00&endtime=2026-02-07T12:00:00&minmagnitude=2.5&limit=20

Important response fields (GeoJSON):
- response['features'] -> list of earthquakes
- each feature:
  - feature['properties']['mag'] (float)
  - feature['properties']['place'] (str)
  - feature['properties']['time'] (int, epoch milliseconds)
  - feature['properties']['url'] (str)
  - feature['geometry']['coordinates'] ([lon, lat, depth_km])
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests


USGS_QUERY_ENDPOINT = "https://earthquake.usgs.gov/fdsnws/event/1/query"
DEFAULT_TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class Quake:
    magnitude: float
    place: str
    time_utc: datetime
    url: str
    lon: float
    lat: float
    depth_km: float


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch and explore recent earthquakes from the USGS API (GeoJSON)."
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=24,
        help="How far back to search (in hours). Default: 24",
    )
    parser.add_argument(
        "--min-mag",
        type=float,
        default=2.5,
        help="Minimum magnitude filter. Default: 2.5",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max number of results to return. Default: 20 (USGS max is 20000)",
    )
    parser.add_argument(
        "--order",
        choices=["time", "magnitude"],
        default="magnitude",
        help="How to sort displayed results. Default: magnitude",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="If set, show a matplotlib plot of magnitude over time.",
    )
    parser.add_argument(
        "--save-plot",
        default=None,
        metavar="PATH",
        help="Optional path to save the plot image (PNG). If omitted, just shows the plot.",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="When used with --save-plot, don't open a plot window (useful on servers).",
    )
    return parser.parse_args(argv)


def isoformat_utc(dt: datetime) -> str:
    """Return ISO 8601 without timezone offset (USGS accepts 'Z' or naive)."""
    dt = dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=None).isoformat(timespec="seconds")


def build_params(
    *, start_utc: datetime, end_utc: datetime, min_mag: float, limit: int
) -> Dict[str, str]:
    return {
        "format": "geojson",
        "starttime": isoformat_utc(start_utc),
        "endtime": isoformat_utc(end_utc),
        "minmagnitude": str(min_mag),
        "limit": str(limit),
        # You can add more params later (e.g., maxradiuskm + latitude + longitude)
    }


def fetch_quakes(params: Dict[str, str]) -> Dict[str, Any]:
    try:
        resp = requests.get(USGS_QUERY_ENDPOINT, params=params, timeout=DEFAULT_TIMEOUT_SECONDS)
    except requests.RequestException as e:
        raise RuntimeError(f"Network error while calling USGS API: {e}") from e

    if resp.status_code != 200:
        # USGS usually returns helpful text on errors.
        raise RuntimeError(
            f"USGS API returned HTTP {resp.status_code}: {resp.text[:300]}"
        )

    try:
        return resp.json()
    except ValueError as e:
        raise RuntimeError("USGS API response was not valid JSON.") from e


def parse_geojson(data: Dict[str, Any]) -> List[Quake]:
    features = data.get("features")
    if not isinstance(features, list):
        raise RuntimeError("Unexpected response: 'features' missing or not a list.")

    quakes: List[Quake] = []
    for f in features:
        try:
            props = f["properties"]
            geom = f["geometry"]
            coords = geom["coordinates"]

            mag = props.get("mag")
            place = props.get("place") or "(unknown location)"
            t_ms = props.get("time")
            url = props.get("url") or ""

            # coordinates: [longitude, latitude, depth_km]
            lon, lat, depth_km = coords[0], coords[1], coords[2]

            if mag is None or t_ms is None:
                # Skip incomplete entries
                continue

            time_utc = datetime.fromtimestamp(int(t_ms) / 1000, tz=timezone.utc)

            quakes.append(
                Quake(
                    magnitude=float(mag),
                    place=str(place),
                    time_utc=time_utc,
                    url=str(url),
                    lon=float(lon),
                    lat=float(lat),
                    depth_km=float(depth_km),
                )
            )
        except (KeyError, TypeError, ValueError):
            # If the feature doesn't match expected structure, skip it.
            continue

    return quakes


def sort_quakes(quakes: List[Quake], order: str) -> List[Quake]:
    if order == "time":
        return sorted(quakes, key=lambda q: q.time_utc, reverse=True)
    return sorted(quakes, key=lambda q: q.magnitude, reverse=True)


def format_row(q: Quake) -> str:
    # Example: M4.8 | 2026-02-07 04:12 UTC | 10km NW of Somewhere | depth 12.3 km
    t = q.time_utc.strftime("%Y-%m-%d %H:%M UTC")
    return f"M{q.magnitude:.1f} | {t} | depth {q.depth_km:.1f} km | {q.place}"


def print_results(quakes: List[Quake], *, limit: int) -> None:
    if not quakes:
        print("No earthquakes matched your filters.")
        return

    print(f"Found {len(quakes)} earthquakes. Showing up to {min(limit, len(quakes))}:")
    print("-" * 80)
    for i, q in enumerate(quakes[:limit], start=1):
        print(f"{i:>2}. {format_row(q)}")
        if q.url:
            print(f"    USGS page: {q.url}")


def plot_quakes(
    quakes: List[Quake],
    *,
    title: str,
    save_path: Optional[str] = None,
    show: bool = True,
) -> None:
    if not quakes:
        print("No data to plot.")
        return

    # Import here so the script still runs without plotting dependencies if desired.
    import matplotlib
    import matplotlib.pyplot as plt

    if not show:
        matplotlib.use("Agg")

    times = [q.time_utc for q in quakes]
    mags = [q.magnitude for q in quakes]

    plt.figure()
    plt.plot(times, mags, marker="o", linestyle="-")
    plt.xlabel("Time (UTC)")
    plt.ylabel("Magnitude")
    plt.title(title)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=200)
        print(f"Saved plot to: {save_path}")

    if show:
        plt.show()
    else:
        plt.close()


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    if args.hours <= 0:
        print("--hours must be > 0", file=sys.stderr)
        return 2
    if args.limit <= 0:
        print("--limit must be > 0", file=sys.stderr)
        return 2

    end_utc = datetime.now(timezone.utc)
    start_utc = end_utc - timedelta(hours=float(args.hours))

    params = build_params(
        start_utc=start_utc,
        end_utc=end_utc,
        min_mag=float(args.min_mag),
        limit=int(args.limit),
    )

    data = fetch_quakes(params)
    quakes = parse_geojson(data)

    # Display sorting is separate from API limit.
    quakes_sorted = sort_quakes(quakes, args.order)
    print_results(quakes_sorted, limit=args.limit)

    if args.plot or args.save_plot:
        title = f"Earthquakes past {args.hours:g}h (min M{args.min_mag:g})"
        # Plot in chronological order for readability
        quakes_by_time = sort_quakes(quakes, "time")
        plot_quakes(
            quakes_by_time,
            title=title,
            save_path=args.save_plot,
            show=(not args.no_show),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
