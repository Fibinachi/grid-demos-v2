"""
gw_geo — Centralized GrantWizard Geocoding & Spatial Analysis
===============================================================
Single source of truth for ALL geocoding, reverse geocoding, spatial analysis,
and geographic data enrichment. Every scraper and pipeline imports from here.

Usage:
    from gw_geo import census, here, mapbox, tracts, market

    # Geocode an address
    lat, lng, source = census.geocode_street("123 Main St", "Columbia", "SC", "29210")
    lat, lng, source = here.geocode("First Baptist Church", "Columbia", "SC")
    lat, lng, source = mapbox.geocode("123 Main St", "Columbia", "SC", "29210")

    # Reverse geocode to tract
    tract_fips = tracts.reverse(lat, lng)

    # Load market data
    cbsa = market.load_cbsa()
"""

__version__ = "1.0.0"
