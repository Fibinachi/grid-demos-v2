"""
Explore encoding recovery for garbled Tamil PDF text.
Test if the garbled text can be decoded back to proper Tamil.
"""
from pypdf import PdfReader
import sys

reader = PdfReader(r'E:\grid\heritagetemples_non_listed.pdf')
page = reader.pages[2]
raw_text = page.extract_text()

# Let's try to get the raw content stream bytes to see what's really stored
stream = page.get_contents()
if stream:
    raw_data = stream.get_data()
    print(f"Raw content stream: {len(raw_data)} bytes")
    # Print hex of first 200 bytes
    print("First 200 bytes (hex):")
    print(raw_data[:200].hex())
    print()
    # Try to find text operations in the PDF stream
    # PDF text is usually between parentheses in Tj operations
    text_parts = []
    i = 0
    while i < len(raw_data):
        # Look for text between parentheses followed by Tj
        if raw_data[i:i+1] == b'(':
            depth = 1
            j = i + 1
            while j < len(raw_data) and depth > 0:
                if raw_data[j:j+1] == b'(' and raw_data[j-1:j] != b'\\':
                    depth += 1
                elif raw_data[j:j+1] == b')' and raw_data[j-1:j] != b'\\':
                    depth -= 1
                j += 1
            txt = raw_data[i+1:j-1]
            # Check for Tj after this
            rest = raw_data[j:j+5]
            if b'Tj' in rest or b'TJ' in rest:
                text_parts.append(txt)
                if len(text_parts) >= 5:
                    break
            i = j
        else:
            i += 1
    
    print(f"Found {len(text_parts)} text operations:")
    for idx, tp in enumerate(text_parts):
        print(f"  {idx}: raw bytes={tp[:50].hex()} | ascii={tp[:50]}")

# Also check if there's a CMap ToUnicode stream we can inspect
print("\n--- Checking CMap ---")
resources = page.get('/Resources', {})
fonts = resources.get('/Font', {})

for key, font in fonts.items():
    if '/ToUnicode' in font:
        try:
            cmap = font['/ToUnicode']
            if hasattr(cmap, 'get_data'):
                data = cmap.get_data()
            else:
                # Try to get stream
                data = cmap._data if hasattr(cmap, '_data') else str(cmap).encode()
            print(f"\nFont {key} ToUnicode ({len(data)} bytes):")
            decoded = data.decode('ascii', errors='replace')
            # Print first 50 lines
            for line in decoded.split('\n')[:30]:
                print(f"  {line}")
        except Exception as e:
            print(f"Font {key} error: {e}")
