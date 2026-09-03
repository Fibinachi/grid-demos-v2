"""Build the district mapping from the PDF table of contents."""
import fitz

doc = fitz.open(r'E:\grid\heritagetemples_non_listed.pdf')
page = doc[1]  # Page 2 = table of contents
text = page.get_text()

print("=== RAW TABLE OF CONTENTS ===")
print(text)
doc.close()
