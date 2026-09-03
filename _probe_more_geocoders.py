#!/usr/bin/env python
"""Probe additional geocoding servers that could parallelize the round-robin.

Tests (read-only, 1 request each):
  1. nominatim.openstreetmap.fr      - public Nominatim mirror (free, no key)
  2. geocode.maps.co                 - already in round-robin (reverse); also forward?
  3. photon.komoot.io                - already in round-robin
  4. Mapbox FORWARD (api.mapbox.com/geocoding/v5/mapbox.places/) - key on hand
  5. geocode.earth FORWARD (Pelias /v1/search) - key on hand
  6. US Census Geocoder (batch, free, no key) - US addresses only
  7. BAN France (api-adresse.data.gouv.fr) - free, France only

Each test prints server, endpoint, status, sample result.
"""

import json
import os
import sys
import urllib.parse
import urllib.request

UA = "GRID/1.0 (https://github.com/grid; academic research; contact charles@gridataset.com)"


def get(url, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        b = r.read()
        return b if raw else b.decode("utf-8", errors="replace")


def probe(name, url):
    try:
        txt = get(url)
        print(f"[OK] {name}\n     {url[:110]}")
        print(f"     -> {txt[:180].replace(chr(10), ' ')}")
    except Exception as e:
        print(f"[x]  {name}: {e}")
    print()


def main():
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    q = urllib.parse.quote

    # 1) French OSM Nominatim mirror (free public)
    probe("nominatim.openstreetmap.fr (Nominatim reverse)",
          "https://nominatim.openstreetmap.fr/reverse?lat=48.8534&lon=2.3488"
          "&format=json&addressdetails=1&accept-language=en")

    # 2) geocode.maps.co reverse (already a provider)
    probe("geocode.maps.co (Nominatim reverse, key on hand)",
          "https://geocode.maps.co/reverse?lat=48.8534&lon=2.3488"
          "&api_key=6812538a6a350959687023hqb35f651")

    # 3) Photon reverse (already a provider)
    probe("photon.komoot.io (reverse)",
          "https://photon.komoot.io/reverse?lon=2.3488&lat=48.8534")

    # 4) Mapbox FORWARD geocoding (key on hand)
    mk = os.environ.get("MAPBOX_API_KEY", "")
    if not mk:
        raise ValueError("MAPBOX_API_KEY environment variable is required")
    probe("Mapbox FORWARD (mapbox.places)",
          f"https://api.mapbox.com/geocoding/v5/mapbox.places/"
          f"{q('Notre-Dame de Paris')}.json?proximity=2.3488,48.8534"
          f"&limit=1&access_token={mk}")

    # 5) geocode.earth FORWARD (Pelias search, key on hand)
    ek = os.environ.get("GEOCODE_EARTH_API_KEY", "")
    if not ek:
        raise ValueError("GEOCODE_EARTH_API_KEY environment variable is required")
    probe("geocode.earth FORWARD (Pelias /v1/search)",
          f"https://api.geocode.earth/v1/search?text={q('Notre-Dame de Paris')}"
          f"&boundary.rect.min_lon=2.30&boundary.rect.min_lat=48.80"
          f"&boundary.rect.max_lon=2.40&boundary.rect.max_lat=48.90"
          f"&size=1&api_key={ek}")

    # 6) US Census Geocoder (free, no key, batch 1000/req)
    probe("US Census Geocoder (address batch)",
          "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?"
          "address=4600%20Silver%20Hill%20Rd%2C%20Washington%2C%20DC%2020233"
          "&benchmark=Public_AR_Current&format=json")

    # 7) BAN France (free, no key, France-only)
    probe("BAN France (api-adresse.data.gouv.fr)",
          "https://api-adresse.data.gouv.fr/search/?q=8%20bd%20du%20port&limit=1")


if __name__ == "__main__":
    main()
