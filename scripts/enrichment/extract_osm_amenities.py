#!/usr/bin/env python3
"""
Extract hospitals, clinics, fire stations, and police stations from an OSM PBF file.
Usage: python extract_osm_amenities.py <input.pbf> <output.csv>
"""

import sys
import csv
import osmium

AMENITIES = {'hospital', 'clinic', 'fire_station', 'police'}

class AmenityHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.results = []  # (lat, lon, amenity, name)
        self.count = 0

    def node(self, n):
        tags = dict(n.tags)
        amenity = tags.get('amenity')
        if amenity in AMENITIES:
            self.results.append((n.location.lat, n.location.lon, amenity, tags.get('name', '')))
            self.count += 1
            if self.count % 10000 == 0:
                print(f'\r  Found {self.count:,}...', end='', file=sys.stderr)

    def way(self, w):
        tags = dict(w.tags)
        amenity = tags.get('amenity')
        if amenity in AMENITIES:
            # For ways, compute centroid from nodes
            if len(w.nodes) > 0:
                lat = sum(n.location.lat for n in w.nodes if n.location.valid()) / len(w.nodes)
                lon = sum(n.location.lon for n in w.nodes if n.location.valid()) / len(w.nodes)
                self.results.append((lat, lon, amenity, tags.get('name', '')))
                self.count += 1
                if self.count % 10000 == 0:
                    print(f'\r  Found {self.count:,}...', end='', file=sys.stderr)


def main():
    if len(sys.argv) < 3:
        print('Usage: python extract_osm_amenities.py <input.pbf> <output.csv>')
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    
    print(f'Extracting amenities from {input_path}...', file=sys.stderr)
    handler = AmenityHandler()
    handler.apply_file(input_path, locations=True, idx='flex_mem')
    
    # Write CSV
    print(f'\nWriting {handler.count:,} results to {output_path}...', file=sys.stderr)
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['lat', 'lon', 'amenity', 'name'])
        for row in handler.results:
            writer.writerow(row)
    
    print(f'Done. Found {handler.count:,} amenities.', file=sys.stderr)


if __name__ == '__main__':
    main()
