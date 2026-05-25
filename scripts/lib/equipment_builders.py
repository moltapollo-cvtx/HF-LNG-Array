"""Typed equipment builders. One function per equipment type.

Each builder is responsible for:
  - placing one or more Blender primitives at `pos`
  - rotating them about Z by `rotation` degrees (pivoting at the footprint
    center, which is `pos[:2]`). No-op when rotation == 0.
  - emitting a Blender Empty named `anchor_<id>` at `pos`; this is the
    named feature anchor that cinematics target via lookAt.

Signature for every builder:
    build_<type>(bpy, mats, eq_id: str, pos, rotation: float, assumptions: dict) -> None

Geometry is moved here verbatim from build_scene() — coordinates re-expressed
relative to `pos` instead of derived from option metadata.
"""
from __future__ import annotations
import math
from typing import Callable


# ---------------------------------------------------------------------------
# Local primitive helpers — duplicated from generate_lng_site_blender.py so
# this module has no import-time dependency on the generator script. Keeping
# them local also lets Task 7 wire build_from_site() without circular imports.
# ---------------------------------------------------------------------------


def _assign(obj, mat) -> None:
    if mat:
        obj.data.materials.append(mat)


def _add_cube(bpy, name, location, dimensions, mat=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    _assign(obj, mat)
    return obj


def _add_cylinder_x(bpy, name, location, length, radius, mat=None, vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=length, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler[1] = math.radians(90)
    _assign(obj, mat)
    return obj


def _add_cylinder_z(bpy, name, location, depth, radius, mat=None, vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    _assign(obj, mat)
    return obj


def _add_pipe(bpy, name, points, radius, mat=None):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = radius
    curve.bevel_resolution = 5
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, coords in zip(spline.points, points):
        point.co = (coords[0], coords[1], coords[2], 1.0)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    _assign(obj, mat)
    return obj


def _add_label(bpy, name, text, location, size, mat=None):
    bpy.ops.object.text_add(location=location, rotation=(0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    obj.data.body = text
    obj.data.align_x = "CENTER"
    obj.data.align_y = "CENTER"
    obj.data.size = size
    _assign(obj, mat)
    bpy.ops.object.convert(target="MESH")
    bpy.context.object.name = name
    return bpy.context.object


def _add_trailer_tank(bpy, mats, name, x, y, dims):
    length = dims["length"]
    width = dims["width"]
    objs = []
    objs.append(_add_cube(bpy, f"{name} trailer frame", (x, y, 0.55), (length, width, 0.35), mats["skid"]))
    objs.append(_add_cylinder_x(bpy, f"{name} pressure vessel", (x, y, 2.15), length * 0.88, 1.18, mats["iso_tank"], vertices=64))
    objs.append(_add_cube(bpy, f"{name} controls cabinet", (x + length * 0.34, y - width * 0.55, 1.35), (1.1, 0.2, 1.0), mats["apollo_navy"]))
    objs.append(_add_cylinder_z(bpy, f"{name} wheel set A", (x - length * 0.32, y - width * 0.56, 0.42), 0.16, 0.42, mats["road"], vertices=32))
    objs.append(_add_cylinder_z(bpy, f"{name} wheel set B", (x + length * 0.32, y - width * 0.56, 0.42), 0.16, 0.42, mats["road"], vertices=32))
    return objs


def _add_equipment_skid(bpy, mats, name, x, y, dims, label):
    length, width, height = dims
    objs = []
    objs.append(_add_cube(bpy, f"{name} base", (x, y, 0.25), (length, width, 0.5), mats["skid"]))
    objs.append(_add_cube(bpy, f"{name} package enclosure", (x, y, 0.55 + height / 2), (length * 0.82, width * 0.72, height), mats["apollo_navy"]))
    objs.append(_add_cube(bpy, f"{name} service clearance", (x, y, 0.04), (length + 1.8, width + 1.4, 0.04), mats["apollo_gold"]))
    objs.append(_add_label(bpy, f"{name} label", label, (x, y, 0.09), 0.9, mats["label"]))
    return objs


# ---------------------------------------------------------------------------
# Anchor + rotation helpers
# ---------------------------------------------------------------------------


def _add_anchor(bpy, name: str, pos) -> None:
    """Create an Empty at pos named `anchor_<name>`. Cinematics target this."""
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=tuple(pos))
    bpy.context.object.name = f"anchor_{name}"


def _rotate_z(obj, rotation_deg: float, pivot) -> None:
    """Rotate an object about Z by rotation_deg, pivoting at (pivot.x, pivot.y).
    No-op when rotation_deg == 0.
    """
    if rotation_deg == 0:
        return
    rad = math.radians(rotation_deg)
    dx = obj.location.x - pivot[0]
    dy = obj.location.y - pivot[1]
    obj.location.x = pivot[0] + dx * math.cos(rad) - dy * math.sin(rad)
    obj.location.y = pivot[1] + dx * math.sin(rad) + dy * math.cos(rad)
    obj.rotation_euler = (obj.rotation_euler[0], obj.rotation_euler[1], rad)


def _rotate_all(objs, rotation_deg: float, pivot) -> None:
    if rotation_deg == 0:
        return
    for obj in objs:
        if obj is None:
            continue
        _rotate_z(obj, rotation_deg, pivot)


# ---------------------------------------------------------------------------
# Builders — one per EQUIPMENT_TYPES entry. Geometry is ported verbatim from
# build_scene() in generate_lng_site_blender.py, with coordinates re-expressed
# relative to `pos` (the new world position) and `assumptions` (scale hints).
# ---------------------------------------------------------------------------


def build_iso_unit(bpy, mats, eq_id: str, pos, rotation: float, assumptions: dict) -> None:
    """Single ISO container with vessel + LNG fill + frame rails + corner posts + valve cabinet.

    Ported from add_iso_unit (lines 249-270) called inside the array loop at line 333.
    """
    iso = assumptions["isoContainer"]
    length = iso["length"]
    width = iso["width"]
    height = iso["height"]
    radius = iso["tankRadius"]
    x, y = pos[0], pos[1]
    z_base = 0.18 + pos[2]
    z_mid = z_base + height * 0.52

    objs = []
    objs.append(_add_cylinder_x(bpy, f"ISO {eq_id} insulated LNG vessel", (x, y, z_mid), length, radius, mats["iso_tank"], vertices=64))
    objs.append(_add_cylinder_x(bpy, f"ISO {eq_id} static LNG fill volume", (x, y, z_mid - 0.18), length * 0.94, radius * 0.82, mats["lng"], vertices=48))

    rail_z_low = z_base + 0.15
    rail_z_high = z_base + height - 0.12
    for side_y in (y - width / 2, y + width / 2):
        objs.append(_add_cube(bpy, f"ISO {eq_id} side rail lower", (x, side_y, rail_z_low), (length, 0.08, 0.08), mats["iso_frame"]))
        objs.append(_add_cube(bpy, f"ISO {eq_id} side rail upper", (x, side_y, rail_z_high), (length, 0.08, 0.08), mats["iso_frame"]))
    for end_x in (x - length / 2, x + length / 2):
        for side_y in (y - width / 2, y + width / 2):
            objs.append(_add_cube(bpy, f"ISO {eq_id} corner post", (end_x, side_y, z_base + height / 2), (0.12, 0.12, height), mats["iso_frame"]))

    objs.append(_add_cube(bpy, f"ISO {eq_id} valve cabinet", (x + length * 0.38, y - width * 0.58, z_base + 1.0), (0.75, 0.16, 0.72), mats["apollo_navy"]))

    _rotate_all(objs, rotation, pos)
    _add_anchor(bpy, eq_id, pos)


def build_truck_bay(bpy, mats, eq_id: str, pos, rotation: float, assumptions: dict) -> None:
    """Transport offload bay: paved cube + LNG transport trailer + label.

    Ported from build_scene lines 348-352.
    """
    bay = assumptions["truckBay"]
    x, y = pos[0], pos[1]
    z0 = pos[2]
    objs = []
    objs.append(_add_cube(bpy, f"{eq_id} transport offload bay pavement", (x, y, z0 + 0.03), (bay["length"], bay["width"], 0.06), mats["road"]))
    objs.extend(_add_trailer_tank(bpy, mats, f"{eq_id} LNG transport offload", x, y, {"length": 18.0, "width": 2.55, "height": 3.3}))
    objs.append(_add_label(bpy, f"{eq_id} truck bay label", "TRANSPORT OFFLOAD BAY", (x, y + 4.4, z0 + 0.09), 0.85, mats["label"]))

    _rotate_all(objs, rotation, pos)
    _add_anchor(bpy, eq_id, pos)


def build_pipe_manifold(bpy, mats, eq_id: str, pos, rotation: float, assumptions: dict) -> None:
    """Cryogenic pipe manifold rendered as a horizontal pipe run with branch stubs.

    Ported from build_scene lines 336-340 (the common cryogenic ISO manifold +
    branch headers). assumptions["pipeManifold"] is a scale hint only; radius
    and pipe count are literal as in the original.
    """
    manifold = assumptions["pipeManifold"]
    length = manifold["length"]
    x, y = pos[0], pos[1]
    z = pos[2] + 1.0
    half = length / 2
    objs = []
    # Main cryo header run along X — the cylinder/pipe described in Task 3.
    objs.append(_add_pipe(
        bpy,
        f"{eq_id} common cryogenic ISO manifold",
        [(x - half, y, z), (x + half, y, z)],
        0.12,
        mats["cryo"],
    ))
    # Three branch stubs (one at each quarter point) — visual hint at branch headers.
    for frac in (-0.33, 0.0, 0.33):
        bx = x + frac * length
        objs.append(_add_pipe(
            bpy,
            f"{eq_id} branch header",
            [(bx, y, z), (bx, y + 3.0, z)],
            0.055,
            mats["cryo"],
        ))

    _rotate_all(objs, rotation, pos)
    _add_anchor(bpy, eq_id, pos)


def build_queens_pair(bpy, mats, eq_id: str, pos, rotation: float, assumptions: dict) -> None:
    """Pair of HP Smart Queen trailers placed side-by-side along X.

    Ported from build_scene lines 342-346. Original placed two trailers 16.5m
    apart; here we keep the same offset, centered on `pos`.
    """
    queen = assumptions["queenTrailer"]
    x, y = pos[0], pos[1]
    z0 = pos[2]
    offset = 16.5
    # Center the pair on pos: shift left/right by offset/2 so anchor sits between them.
    left_x = x - offset / 2
    right_x = x + offset / 2
    objs = []
    objs.extend(_add_trailer_tank(bpy, mats, f"{eq_id} HP Smart Queen 1", left_x, y, queen))
    objs.extend(_add_trailer_tank(bpy, mats, f"{eq_id} HP Smart Queen 2", right_x, y, queen))
    objs.append(_add_label(bpy, f"{eq_id} queens label", "2x HP SMART QUEENS", (x, y - 4.2, z0 + 0.09), 0.9, mats["label"]))

    _rotate_all(objs, rotation, pos)
    _add_anchor(bpy, eq_id, pos)


def build_glycol_vaporizer_with_stack(bpy, mats, eq_id: str, pos, rotation: float, assumptions: dict) -> None:
    """Glycol-bath HP vaporizer skid + vertical exhaust stack.

    Ported from build_scene lines 354-369. The stack offset relative to the
    skid center is (+3.2, +1.9, 5.0) in the original.
    """
    vap = assumptions["vaporizerSkid"]
    x, y = pos[0], pos[1]
    z0 = pos[2]
    dims = (vap["length"], vap["width"], vap["height"])
    objs = []
    objs.extend(_add_equipment_skid(bpy, mats, f"{eq_id} vaporizer skid", x, y, dims, "GLYCOL-BATH HP VAPORIZER"))
    objs.append(_add_cylinder_z(
        bpy,
        f"{eq_id} vaporizer stack",
        (x + 3.2, y + 1.9, z0 + 5.0),
        3.8,
        0.36,
        mats["skid"],
        vertices=32,
    ))

    _rotate_all(objs, rotation, pos)
    _add_anchor(bpy, eq_id, pos)


def build_bog_skid(bpy, mats, eq_id: str, pos, rotation: float, assumptions: dict) -> None:
    """BOG capture skid — a single packaged equipment skid.

    Ported from build_scene lines 387-402.
    """
    bog = assumptions["bogSkid"]
    x, y = pos[0], pos[1]
    dims = (bog["length"], bog["width"], bog["height"])
    objs = list(_add_equipment_skid(bpy, mats, f"{eq_id} BOG capture skid", x, y, dims, "BOG CAPTURE SKID"))

    _rotate_all(objs, rotation, pos)
    _add_anchor(bpy, eq_id, pos)


def build_delivery_flange(bpy, mats, eq_id: str, pos, rotation: float, _assumptions: dict) -> None:
    """Delivery flange riser — a vertical warm-gas cylinder plus label.

    Ported from build_scene lines 404-407 (add_cylinder_z at delivery position).
    Radius (0.32 m) + height (2.2 m) are literals; assumptions block is a
    scale hint that other shape-aware tooling may consume.
    """
    del _assumptions  # required by BUILDERS signature; dims are literals here
    x, y = pos[0], pos[1]
    z0 = pos[2]
    objs = []
    objs.append(_add_cylinder_z(
        bpy,
        f"{eq_id} delivery flange riser",
        (x, y, z0 + 1.1),
        2.2,
        0.32,
        mats["warm"],
        vertices=40,
    ))
    objs.append(_add_label(
        bpy,
        f"{eq_id} delivery flange label",
        "DELIVERY FLANGE 550-650 PSIG",
        (x - 4.7, y + 3.2, z0 + 0.09),
        0.75,
        mats["label"],
    ))

    _rotate_all(objs, rotation, pos)
    _add_anchor(bpy, eq_id, pos)


# ---------------------------------------------------------------------------
# Registry — Task 7 will look up builders here via Equipment.type.
# ---------------------------------------------------------------------------


BUILDERS: dict[str, Callable] = {
    "truck_bay": build_truck_bay,
    "pipe_manifold": build_pipe_manifold,
    "queens_pair": build_queens_pair,
    "glycol_vaporizer_with_stack": build_glycol_vaporizer_with_stack,
    "bog_skid": build_bog_skid,
    "delivery_flange": build_delivery_flange,
    "iso_unit": build_iso_unit,
}
