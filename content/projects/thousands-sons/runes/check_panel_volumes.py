"""
Sanity-check a batch of exported panel STLs by volume.

Every panel in a batch shares the same border cutter (built once, reused
per panel - see any rune_panel_*.py's main()), so panel-to-panel volume
should vary only with the glyph's own carved-out area. A silently broken
boolean (dropped or duplicated geometry - see the v6 fishbone_3strand
incident this script was written after) shows up as an outlier against
that otherwise-tight spread. This is a coarse proxy, not a full mesh
validator: it won't catch a defect that happens to preserve volume, but
those are rare in practice - the failures actually seen here move volume
by a lot.

Usage: python3 check_panel_volumes.py <output_dir> [threshold_fraction]
  threshold_fraction: how far a panel's volume may deviate from the
  batch median before being flagged (default 0.08 = 8%)
"""

import struct
import sys
import os


def stl_volume(path):
    """Signed volume via the divergence theorem, summed over all
    triangles (abs() at the end handles either winding convention).
    Only meaningful for a closed/manifold mesh - that's exactly the
    property a dropped-geometry defect breaks, which is why this
    catches it (a hole in the surface makes the sum not equal the
    true enclosed volume)."""
    with open(path, "rb") as f:
        f.read(80)
        count = struct.unpack("<I", f.read(4))[0]
        vol = 0.0
        for _ in range(count):
            data = f.read(50)
            ax, ay, az, bx, by, bz, cx, cy, cz = struct.unpack("<9f", data[12:48])
            vol += (ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)) / 6.0
        return abs(vol)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    out_dir = sys.argv[1]
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.08

    rows = []
    for fn in sorted(os.listdir(out_dir)):
        if fn.endswith(".stl"):
            rows.append((fn, stl_volume(os.path.join(out_dir, fn))))

    if not rows:
        print(f"No STL files found in {out_dir}")
        sys.exit(1)

    vols = sorted(v for _, v in rows)
    median = vols[len(vols) // 2]

    outliers = []
    for fn, vol in rows:
        frac = abs(vol - median) / median if median else 0.0
        flag = frac > threshold
        if flag:
            outliers.append((fn, vol, frac))
        print(f"{fn:35s} vol={vol:9.2f}{'  <-- OUTLIER (' + f'{frac:.0%}' + ' off median)' if flag else ''}")

    print(f"\n{len(rows)} panels, median volume {median:.2f}, threshold {threshold:.0%}")
    if outliers:
        print(f"{len(outliers)} OUTLIER(S) - check these before printing:")
        for fn, vol, frac in outliers:
            print(f"  {fn}: {vol:.2f} ({frac:.0%} off median)")
        sys.exit(1)
    else:
        print("All panels within threshold - no outliers.")


if __name__ == "__main__":
    main()
