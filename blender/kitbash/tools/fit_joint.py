"""
Ball/cup joint fitting for kitbash recipes - finds the joint centres and radii that go into
part_joint / body_joint / joint_r, and checks a recipe part is seated in its cup.

Three modes, all writing debug PNGs to --out (default out/fit/):

  overview  three projections of an STL with a mm grid, to read off the box around a joint
      .venv/bin/python tools/fit_joint.py --stl "Body.stl" --overview

  fit       sphere fit to the faces inside a box; --kind cup (hollow, centre outside the solid)
            or ball (centre inside the solid). Prints the TOML line and plots three section cuts
            through the fitted centre with the circle drawn on.
      .venv/bin/python tools/fit_joint.py --stl "Body.stl" --kind cup --box -3 -10 3 5 -2 11

  check     places a recipe part the way kitbash does (snap, rest_rot, offset) and plots three
            section cuts through the recipe's cup (body_joint, joint_r) with the pivot marked -
            review the part's outline against the cup circle.
      .venv/bin/python tools/fit_joint.py --recipe recipes/lokhust.toml --check head

Fit method: every face votes for a centre one radius along its normal (outward for a cup,
inward for a ball), area-weighted, over a range of radii; the densest 0.1mm cell wins, then a
least-squares sphere through the faces that support it refines centre and radius. The box keeps
other round surfaces out of the vote - make it hug the joint. Normals come from the STL's
triangle winding, so the mesh needs consistent outward normals.
"""
import argparse
import os
import sys
import tomllib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np               # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CELL = 0.1          # vote grid cell, mm
MAX_CELLS = 400     # per axis; larger boxes get a coarser cell
SUPPORT_TOL = 0.15  # mm off the sphere still counted as supporting it
DRIFT_WARN = 0.2    # mm the centre may move when the box is resized 20% before warning


# --- STL / recipe -------------------------------------------------------------------------

def read_stl(path):
    """Triangles (N, 3, 3) from a binary or ASCII STL."""
    with open(path, "rb") as f:
        data = f.read()
    n = int.from_bytes(data[80:84], "little") if len(data) >= 84 else 0
    if len(data) == 84 + 50 * n:
        rec = np.frombuffer(data, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)),
                                                  ("a", "<u2")]), count=n, offset=84)
        return rec["v"].astype(np.float64)
    v = [list(map(float, ln.split()[1:4])) for ln in data.decode(errors="ignore").splitlines()
         if ln.strip().startswith("vertex")]
    return np.array(v, np.float64).reshape(-1, 3, 3)


def load_recipe(path):
    with open(path, "rb") as f:
        r = tomllib.load(f)
    r["source"] = os.path.expanduser(r["source"])
    r["data"] = os.path.expanduser(r.get("data", ROOT))
    return r


def source_path(recipe, filename):
    """Same rule as kitbash: the prepped file in parts/<name>/ wins over the source file."""
    prepped = os.path.join(recipe["data"], "parts", recipe["name"], filename)
    return prepped if os.path.exists(prepped) else os.path.join(recipe["source"], filename)


def rotation(angles):
    """kitbash's rest/pose rotation: yaw (Z), then pitch (X), then roll (Y), degrees."""
    y, p, r = (np.radians(angles.get(k, 0.0)) for k in ("yaw", "pitch", "roll"))
    Rz = np.array([[np.cos(y), -np.sin(y), 0], [np.sin(y), np.cos(y), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, np.cos(p), -np.sin(p)], [0, np.sin(p), np.cos(p)]])
    Ry = np.array([[np.cos(r), 0, np.sin(r)], [0, 1, 0], [-np.sin(r), 0, np.cos(r)]])
    return Rz @ Rx @ Ry


def place(tris, part):
    """A recipe part's triangles in the body frame at rest, as kitbash places it."""
    centre = np.array(part["body_joint"]) + np.array(part.get("offset", (0, 0, 0)))
    R = rotation(part.get("rest_rot", {}))
    return centre + (tris - np.array(part["part_joint"])) @ R.T, centre


# --- fitting ------------------------------------------------------------------------------

def fit_sphere(tris, lo, hi, kind, r_min, r_max):
    """(centre, radius, n_support) of the best cup/ball in the box, or None."""
    sign = 1.0 if kind == "cup" else -1.0
    cen = tris.mean(1)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    area = np.linalg.norm(n, axis=1) / 2
    n /= np.linalg.norm(n, axis=1)[:, None] + 1e-12
    m = np.all((cen > lo) & (cen < hi), axis=1)
    cen, n, area = cen[m], n[m], area[m]
    if len(cen) < 20:
        return None
    cell = max(CELL, (hi - lo).max() / MAX_CELLS)
    bins = [np.arange(l, h + cell, cell) for l, h in zip(lo, hi)]
    best = None
    for r in np.arange(r_min, r_max + 1e-9, cell / 2):
        H, edges = np.histogramdd(cen + sign * r * n, bins=bins, weights=area)
        i = np.unravel_index(H.argmax(), H.shape)
        if best is None or H[i] > best[0]:
            best = (H[i], r, np.array([edges[k][i[k]] + cell / 2 for k in range(3)]))
    _, r, c = best
    to_c = c - cen
    dist = np.linalg.norm(to_c, axis=1)
    facing = np.einsum("ij,ij->i", sign * to_c, n) > 0.8 * dist
    s = cen[(np.abs(dist - r) < SUPPORT_TOL) & facing]
    if len(s) < 10:
        return c, r, len(s)
    A = np.c_[2 * s, np.ones(len(s))]
    x = np.linalg.lstsq(A, (s ** 2).sum(1), rcond=None)[0]
    return x[:3], float(np.sqrt(x[3] + (x[:3] ** 2).sum())), len(s)


def box_drift(tris, lo, hi, kind, r_min, r_max, c):
    """How far the centre moves when the box shrinks / grows 20% about its middle, mm.
    Large drift = the joint isn't a clean sphere (oval dome, shaped socket) and the centre
    depends on what the box covers - treat the fit as a starting point and set offset by eye."""
    mid, half = (lo + hi) / 2, (hi - lo) / 2
    d = []
    for k in (0.8, 1.2):
        res = fit_sphere(tris, mid - half * k, mid + half * k, kind, r_min, r_max)
        if res is not None:
            d.append(np.linalg.norm(res[0] - c))
    return max(d) if d else float("nan")


# --- plots --------------------------------------------------------------------------------

VIEWS = [(0, "SIDE  cut x = {:.2f}   (Y, Z)", (1, 2)),
         (2, "TOP  cut z = {:.2f}   (X, Y)", (0, 1)),
         (1, "FRONT  cut y = {:.2f}   (X, Z)", (0, 2))]


def section(tris, axis, value):
    """Line segments (M, 2, 3) where the plane coord[axis] = value cuts the triangles."""
    d = tris[..., axis] - value
    keep = (d.min(1) < 0) & (d.max(1) > 0)
    t, d = tris[keep], d[keep]
    segs = []
    for i in range(3):
        a, b, da, db = t[:, i], t[:, (i + 1) % 3], d[:, i], d[:, (i + 1) % 3]
        cross = (da > 0) != (db > 0)
        p = np.full_like(a, np.nan)
        p[cross] = a[cross] + (b[cross] - a[cross]) * (da[cross] / (da[cross] - db[cross]))[:, None]
        segs.append(p)
    segs = np.stack(segs, 1)                              # (M, 3 edges, 3)
    ok = ~np.isnan(segs[..., 0])
    two = ok.sum(1) == 2
    if not two.any():
        return np.empty((0, 2, 3))
    return np.stack([s[o] for s, o in zip(segs[two], ok[two])])


def plot_sections(path, title, at, half, shells, circles, box=None):
    """shells: [(tris, colour, label)]; circles: [(centre, r, style, label)], cut through `at`."""
    fig, axs = plt.subplots(1, 3, figsize=(21, 7.5))
    th = np.linspace(0, 2 * np.pi, 200)
    for a, (ax_i, name, (u, v)) in zip(axs, VIEWS):
        for tris, col, lab in shells:
            near = np.all(np.abs(tris.mean(1) - at) < half * 1.5, axis=1)
            S = section(tris[near], ax_i, at[ax_i]) if near.any() else np.empty((0, 2, 3))
            if len(S):                                    # NaN-separated: one plot call per shell
                gap = np.full(len(S), np.nan)
                a.plot(np.c_[S[:, :, u], gap].ravel(), np.c_[S[:, :, v], gap].ravel(), color=col, lw=0.8)
            a.plot([], [], color=col, label=lab)
        for c, r, style, lab in circles:
            a.plot(c[u] + r * np.cos(th), c[v] + r * np.sin(th), style, lw=1.2, label=lab)
            a.plot(c[u], c[v], style[0] + "+", ms=12)
        if box is not None:
            lo, hi = box
            a.add_patch(plt.Rectangle((lo[u], lo[v]), hi[u] - lo[u], hi[v] - lo[v], fill=False,
                                      ls=":", color="tab:green", label="box"))
        a.set_xlim(at[u] - half, at[u] + half)
        a.set_ylim(at[v] - half, at[v] + half)
        a.set_aspect("equal")
        a.grid(alpha=0.3)
        a.set_title(name.format(at[ax_i]))
        a.legend(loc="lower right")
    fig.suptitle(title)
    plt.tight_layout()
    plt.savefig(path, dpi=110)
    plt.close(fig)
    print(f"PNG {path}")


def plot_overview(path, tris):
    """Three vertex-cloud projections with a mm grid, for picking a joint box."""
    v = tris.reshape(-1, 3)
    if len(v) > 300_000:
        v = v[np.random.default_rng(0).choice(len(v), 300_000, replace=False)]
    fig, axs = plt.subplots(1, 3, figsize=(21, 7.5))
    for a, (_, name, (u, w)), title in zip(axs, VIEWS, ("SIDE  (Y, Z)", "TOP  (X, Y)", "FRONT  (X, Z)")):
        a.scatter(v[:, u], v[:, w], s=0.05, c="0.3", linewidths=0)
        a.set_aspect("equal")
        a.minorticks_on()
        a.grid(which="major", alpha=0.5)
        a.grid(which="minor", alpha=0.15)
        a.set_xlabel("XYZ"[u])
        a.set_ylabel("XYZ"[w])
        a.set_title(title)
    lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
    fig.suptitle(f"{os.path.basename(path)}   bounds {np.round(lo, 2)} .. {np.round(hi, 2)}")
    plt.tight_layout()
    plt.savefig(path, dpi=110)
    plt.close(fig)
    print(f"PNG {path}")


# --- modes --------------------------------------------------------------------------------

def stem(path):
    return os.path.splitext(os.path.basename(path))[0].replace(" ", "_")


def run_fit(args):
    tris = read_stl(args.stl)
    lo, hi = np.array(args.box[:3]), np.array(args.box[3:])
    res = fit_sphere(tris, lo, hi, args.kind, *args.r)
    if res is None:
        raise SystemExit("too few faces in the box - check the coordinates against --overview")
    c, r, n = res
    drift = box_drift(tris, lo, hi, args.kind, *args.r, c)
    key = "body_joint" if args.kind == "cup" else "part_joint"
    print(f"FIT {args.kind}  centre {np.round(c, 3)}  r {r:.2f}  support {n} faces  box drift {drift:.2f} mm")
    print(f'{key:<11s} = [{c[0]:.3f}, {c[1]:.3f}, {c[2]:.3f}]   # {args.kind} r{r:.2f}')
    if args.kind == "cup":
        print(f"joint_r     = {r:.2f}")
    if n < 200:
        print("WARNING low support - the fit may be on a small feature, check the PNG")
    if drift > DRIFT_WARN:
        print("WARNING centre moves with the box - joint isn't a clean sphere; use as a starting "
              "point, check with --check and set offset by eye")
    half = max(r * 3, (hi - lo).max() / 2 + 1)
    plot_sections(os.path.join(args.out, f"{stem(args.stl)}_{args.kind}_fit.png"),
                  f"{os.path.basename(args.stl)}  {args.kind} r{r:.2f}  support {n}  box drift {drift:.2f} mm", c, half,
                  [(tris, "0.35", "mesh")], [(c, r, "r--", f"fit r{r:.2f}")], box=(lo, hi))


def run_overview(args):
    plot_overview(os.path.join(args.out, f"{stem(args.stl)}_overview.png"), read_stl(args.stl))


def run_check(args):
    recipe = load_recipe(args.recipe)
    part = next((p for p in recipe["part"] if p["name"] == args.check), None)
    if part is None:
        raise SystemExit(f"no part '{args.check}' in {args.recipe}")
    body = read_stl(source_path(recipe, recipe["body"]))
    placed, centre = place(read_stl(source_path(recipe, part["file"])), part)
    cup_c, cup_r = np.array(part["body_joint"]), part["joint_r"]
    off = centre - cup_c
    print(f"CHECK {part['name']}: cup r{cup_r:.2f} at {np.round(cup_c, 2)}   pivot {np.round(centre, 2)}"
          f"   offset {np.round(off, 2)} ({np.linalg.norm(off):.2f} mm)")
    title = (f"{recipe['name']} / {part['name']}  at rest   cup r{cup_r:.2f}   "
             f"offset {np.round(off, 2).tolist()}")
    circles = [(cup_c, cup_r, "r--", f"cup (recipe) r{cup_r:.2f}"),
               (centre, 0.0, "b:", "pivot (body_joint + offset)")]
    plot_sections(os.path.join(args.out, f"{recipe['name']}_{part['name']}_check.png"), title,
                  cup_c, cup_r * 3, [(body, "0.35", "body"), (placed, "tab:blue", part["name"])],
                  circles)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stl", help="mesh to fit (overview / fit modes)")
    ap.add_argument("--overview", action="store_true", help="projections with a mm grid")
    ap.add_argument("--kind", choices=("cup", "ball"))
    ap.add_argument("--box", nargs=6, type=float, metavar=("XMIN", "YMIN", "ZMIN", "XMAX", "YMAX", "ZMAX"),
                    help="only faces with their centre in this box vote (the STL's own coordinates)")
    ap.add_argument("--r", nargs=2, type=float, default=(0.8, 4.0), metavar=("MIN", "MAX"),
                    help="radius range to search, mm (default 0.8 4.0)")
    ap.add_argument("--recipe", help="recipe TOML (check mode)")
    ap.add_argument("--check", metavar="PART", help="recipe part name to check against its cup")
    ap.add_argument("--out", help="PNG folder (default: <recipe data>/out/fit with --recipe, else out/fit here)")
    args = ap.parse_args()
    if not args.out:
        data = load_recipe(args.recipe)["data"] if args.recipe else ROOT
        args.out = os.path.join(data, "out", "fit")
    os.makedirs(args.out, exist_ok=True)
    if args.check:
        if not args.recipe:
            ap.error("--check needs --recipe")
        run_check(args)
    elif args.stl and args.overview:
        run_overview(args)
    elif args.stl and args.kind and args.box:
        run_fit(args)
    else:
        ap.error("give --stl --overview, --stl --kind --box, or --recipe --check PART")


if __name__ == "__main__":
    sys.exit(main())
