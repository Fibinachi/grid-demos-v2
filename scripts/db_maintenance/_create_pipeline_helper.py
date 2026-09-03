import json, os

# First, clear existing file
with open('_arcgis_pipeline.py', 'w', encoding='utf-8') as f:
    f.write('#!/usr/bin/env python3\n')

print('Cleared pipeline file')
