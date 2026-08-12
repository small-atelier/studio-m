"""
connector.stl.stl is a constant-cross-section prism extruded straight
along X (dovetail-profile bar, no features besides the two flat end
caps) - unlike the drawer/module family, a pure axial scale does not
distort anything here, so no cut/donor Blender surgery is needed.
Every triangle normal in this file has a zero X-component on the side
walls and a pure +-X normal on the end caps, so remapping only the X
coordinate (x' = xmin + (x - xmin) * factor) leaves every normal
direction exactly correct - just a plain STL read/rewrite in pure
Python.

Anchor: xmin (the lower end cap) is held fixed and the bar grows in
+X, matching the +axis convention used in extend_parts.py.
"""

import struct
import os

SRC = "/Users/mannil/Desktop/studio-m/DRAWERS/connector.stl.stl"
OUT_DIR = "/Users/mannil/Desktop/studio-m/DRAWERS"

TARGETS = [
    ("connector_85mm.stl", 85.0),
    ("connector_220mm.stl", 220.0),
]


def read_stl(path):
    with open(path, "rb") as f:
        header = f.read(80)
        (ntri,) = struct.unpack("<I", f.read(4))
        tris = []
        for _ in range(ntri):
            normal = struct.unpack("<3f", f.read(12))
            verts = [struct.unpack("<3f", f.read(12)) for _ in range(3)]
            (attr,) = struct.unpack("<H", f.read(2))
            tris.append((normal, verts, attr))
    return header, tris


def write_stl(path, header, tris):
    with open(path, "wb") as f:
        f.write(header)
        f.write(struct.pack("<I", len(tris)))
        for normal, verts, attr in tris:
            f.write(struct.pack("<3f", *normal))
            for v in verts:
                f.write(struct.pack("<3f", *v))
            f.write(struct.pack("<H", attr))


def rescale_x(tris, xmin, factor):
    out = []
    for normal, verts, attr in tris:
        new_verts = [(xmin + (x - xmin) * factor, y, z) for (x, y, z) in verts]
        out.append((normal, new_verts, attr))
    return out


def main():
    header, tris = read_stl(SRC)
    xs = [v[0] for _, verts, _ in tris for v in verts]
    xmin, xmax = min(xs), max(xs)
    orig_len = xmax - xmin
    print(f"original length: {orig_len:.3f} mm (x {xmin:.3f} -> {xmax:.3f})")

    for out_name, target_len in TARGETS:
        factor = target_len / orig_len
        new_tris = rescale_x(tris, xmin, factor)
        out_path = os.path.join(OUT_DIR, out_name)
        write_stl(out_path, header, new_tris)
        nxs = [v[0] for _, verts, _ in new_tris for v in verts]
        print(f"OK {out_name:25s} length={max(nxs)-min(nxs):.3f} mm -> {out_path}")


if __name__ == "__main__":
    main()
