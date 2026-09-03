"""Replace REGION_ORDER in _import_osm_all.py with the new sorted order."""
with open('_tile_order_out.txt', 'r') as f:
    new_order = f.read().strip()

with open('_import_osm_all.py', 'r') as f:
    content = f.read()

# Find the old REGION_ORDER block
start = content.find('REGION_ORDER = {')
end = content.find('}\n\nFAITH', start)
if end == -1:
    end = content.find('}\nFAITH', start)

old_block = content[start:end+1]
content = content.replace(old_block, new_order)

with open('_import_osm_all.py', 'w') as f:
    f.write(content)

print("REGION_ORDER updated with 238 entries")
