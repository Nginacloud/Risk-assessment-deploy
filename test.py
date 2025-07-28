import re

text = """Metro-Score© 750 PPI© M3 Probability Of Default© 23%"""

pattern = r"Metro-Score©\s*(\d+)\s*PPI©\s*(M\d)\s*Probability Of Default©\s*(\d+\s?%)"
matches = re.findall(pattern, text, re.IGNORECASE)

print("Found matches:", matches)
breakpoint()
