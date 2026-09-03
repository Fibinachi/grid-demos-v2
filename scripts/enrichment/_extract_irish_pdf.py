"""
Extract text from The Irish Church Directory (1904) PDF.
Pages 15+ have the Diocesan, Parochial, and Clerical directory.
"""
import fitz  # PyMuPDF
import os

pdf_path = 'irish_church_directory_1904.pdf'
out_dir = 'data/irish_directory'
os.makedirs(out_dir, exist_ok=True)

doc = fitz.open(pdf_path)
print(f'Total pages: {len(doc)}')

# Extract all text to one file
with open(f'{out_dir}/full_text.txt', 'w', encoding='utf-8') as f:
    for i in range(len(doc)):
        page = doc[i]
        text = page.get_text()
        f.write(f'\n{"="*60}\n=== PAGE {i+1} ===\n{"="*60}\n')
        f.write(text)
        if (i+1) % 20 == 0:
            print(f'  Extracted page {i+1}/{len(doc)}')

print(f'\nDone. Full text saved to {out_dir}/full_text.txt')

# Quick summary
total_chars = sum(len(doc[i].get_text()) for i in range(len(doc)))
print(f'Total characters: {total_chars:,}')
print(f'Average per page: {total_chars//len(doc):,}')

doc.close()
