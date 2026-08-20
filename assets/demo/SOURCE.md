# Demo Wardrobe Image Sources

The 128 checked-in demo wardrobe images are object records from
[Auckland Museum](https://www.aucklandmuseum.com/collections-research/collections),
discovered through the Wikimedia Commons API. Every selected file is explicitly
published under `CC BY 4.0`; the creator, Commons source page, original media
URL, museum media URL, license, and source dimensions are retained in
`wardrobe.json`.

Source images must be at least 800 pixels on both axes. They are decoded with
Pillow, stripped of embedded metadata, fitted to a 768 x 768 light background,
and encoded as WebP below 250 KB. The selected set contains 128 unique source
URLs and follows these category quotas:

- 32 tops
- 24 bottoms
- 20 outerwear items
- 16 dresses
- 14 pairs of shoes
- 12 bags
- 10 accessories

All four seasons contain at least 25 applicable records and all seven
categories. The images are local demonstration fixtures, not StyleMate
photography or products offered for sale.

Run the local provenance and asset audit with:

```powershell
python scripts/audit_demo_sources.py
```

Candidate discovery and asset rebuilding are intentionally separate so source
review can happen before checked-in fixtures change:

```powershell
python scripts/discover_cc_wardrobe.py
python scripts/download_cc_wardrobe.py
```
