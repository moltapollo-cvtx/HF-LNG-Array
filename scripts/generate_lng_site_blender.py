#!/usr/bin/env python3
"""Generate draft Apollo LNG whole-array models with Blender.

Run dry checks with normal Python:
  python3 scripts/generate_lng_site_blender.py --dry-run --option D

Generate authored Blender and GLB assets:
  blender --background --python scripts/generate_lng_site_blender.py -- --all
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def blender_cli_args(argv: list[str]) -> list[str]:
    if "--" in argv:
        return argv[argv.index("--") + 1 :]
    return argv[1:]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Apollo LNG site geometry in Blender.")
    parser.add_argument("--option", default="D", help="Option letter to generate: A, B, C, D, or E.")
    parser.add_argument("--all", action="store_true", help="Generate all options A-E.")
    parser.add_argument("--dry-run", action="store_true", help="Print generation summary without importing bpy.")
    parser.add_argument("--data", default="models/lng-site/lng-site-options.json", help="Option JSON from export_lng_options.mjs.")
    parser.add_argument("--out", default="models/lng-site", help="Directory for .blend and .glb outputs.")
    parser.add_argument("--site", default=None,
        help="Path to a sites/option-X.yaml. Overrides --option when given.")
    return parser.parse_args(blender_cli_args(argv))


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return project_root() / path


def load_payload(path_value: str) -> dict:
    data_path = resolve_path(path_value)
    if not data_path.exists():
        raise SystemExit(f"Missing options JSON: {data_path}")
    return json.loads(data_path.read_text(encoding="utf8"))


def option_slug(option: dict) -> str:
    return f"option-{option['letter'].lower()}"


def find_option(payload: dict, letter: str) -> dict:
    target = letter.upper()
    for option in payload["options"]:
        if option["letter"] == target:
            return option
    raise SystemExit(f"Unknown option: {letter}")


def component_keys(option: dict) -> list[str]:
    keys = [
        "site-pad",
        "security-fence",
        "access-road",
        "iso-array",
        "hp-smart-queen-1",
        "hp-smart-queen-2",
        "vaporizer-skid",
        "truck-offload-bay",
        "cryo-manifold",
        "warm-gas-header",
        "delivery-flange",
    ]
    if option.get("hasPump"):
        keys.append("pad-pump-skid")
    if option.get("hasCapture"):
        keys.append("bog-capture-skid")
    return keys


def layout_metrics(payload: dict, option: dict) -> dict:
    assumptions = payload["assumptions"]
    iso = assumptions["isoContainer"]
    spacing = assumptions["isoSpacing"]
    array_length = iso["length"] + (option["isoCols"] - 1) * spacing["x"]
    array_width = iso["width"] + (option["isoRows"] - 1) * spacing["y"]
    footprint_area = option["footprintAcres"] * 4046.8564224
    site_length = max(array_length + 70.0, math.sqrt(footprint_area * 1.7))
    site_width = max(array_width + 45.0, footprint_area / site_length)
    return {
        "arrayLength": round(array_length, 3),
        "arrayWidth": round(array_width, 3),
        "siteLength": round(site_length, 3),
        "siteWidth": round(site_width, 3),
        "footprintAreaM2": round(footprint_area, 3),
    }


def dry_run_summary(payload: dict, option: dict, out_value: str) -> dict:
    out_dir = Path(out_value)
    slug = option_slug(option)
    return {
        "option": {
            "letter": option["letter"],
            "title": option["title"],
            "fidelity": payload["fidelity"],
        },
        "outputs": {
            "blend": str(out_dir / f"{slug}.blend"),
            "glb": str(out_dir / f"{slug}.glb"),
        },
        "scene": {
            "isoInstances": option["isoCount"],
            "isoGrid": [option["isoCols"], option["isoRows"]],
            "components": component_keys(option),
            "layout": layout_metrics(payload, option),
        },
    }


def selected_options(payload: dict, args: argparse.Namespace) -> list[dict]:
    if args.all:
        return payload["options"]
    return [find_option(payload, args.option)]


def import_bpy():
    try:
        import bpy  # type: ignore
        from mathutils import Vector  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "Blender Python is required for generation. Run with: "
            "blender --background --python scripts/generate_lng_site_blender.py -- --all"
        ) from exc
    return bpy, Vector


def clear_scene(bpy) -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for collection in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.images):
        for item in list(collection):
            if item.users == 0:
                collection.remove(item)


def make_materials(bpy) -> dict:
    def material(name: str, color: tuple[float, float, float, float], metallic=0.0, roughness=0.72):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = color
            bsdf.inputs["Metallic"].default_value = metallic
            bsdf.inputs["Roughness"].default_value = roughness
            bsdf.inputs["Alpha"].default_value = color[3]
        if color[3] < 1.0:
            mat.blend_method = "BLEND"
            mat.use_screen_refraction = True
            mat.show_transparent_back = True
        return mat

    return {
        "apollo_navy": material("Apollo navy steel", (0.035, 0.095, 0.165, 1.0), metallic=0.2),
        "apollo_gold": material("Apollo gold nameplate", (0.72, 0.55, 0.23, 1.0), metallic=0.1),
        "pad": material("Concrete site pad", (0.54, 0.56, 0.56, 1.0)),
        "road": material("Compacted access road", (0.20, 0.21, 0.22, 1.0)),
        "fence": material("Galvanized fence", (0.50, 0.54, 0.56, 1.0), metallic=0.35),
        "iso_frame": material("ISO structural frame", (0.06, 0.13, 0.21, 1.0), metallic=0.25),
        "iso_tank": material("White insulated LNG ISO vessel", (0.86, 0.89, 0.89, 1.0), metallic=0.08),
        "lng": material("Static LNG inventory volume", (0.02, 0.64, 0.90, 0.42), roughness=0.25),
        "cryo": material("Cryogenic LNG route", (0.00, 0.58, 0.88, 1.0), metallic=0.15),
        "warm": material("Warm gas route", (0.92, 0.44, 0.15, 1.0), metallic=0.1),
        "skid": material("Packaged equipment skid", (0.18, 0.23, 0.27, 1.0), metallic=0.2),
        "truck": material("Transport trailer", (0.82, 0.84, 0.83, 1.0), metallic=0.12),
        "label": material("Black engraved labels", (0.02, 0.025, 0.03, 1.0)),
    }


def assign(obj, mat) -> None:
    if mat:
        obj.data.materials.append(mat)


def add_cube(bpy, name: str, location: tuple[float, float, float], dimensions: tuple[float, float, float], mat=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign(obj, mat)
    return obj


def add_cylinder_x(bpy, name: str, location: tuple[float, float, float], length: float, radius: float, mat=None, vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=length, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler[1] = math.radians(90)
    assign(obj, mat)
    return obj


def add_cylinder_z(bpy, name: str, location: tuple[float, float, float], depth: float, radius: float, mat=None, vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    assign(obj, mat)
    return obj


def add_pipe(bpy, name: str, points: list[tuple[float, float, float]], radius: float, mat=None):
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
    assign(obj, mat)
    return obj


def add_label(bpy, name: str, text: str, location: tuple[float, float, float], size: float, mat=None):
    bpy.ops.object.text_add(location=location, rotation=(0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    obj.data.body = text
    obj.data.align_x = "CENTER"
    obj.data.align_y = "CENTER"
    obj.data.size = size
    assign(obj, mat)
    bpy.ops.object.convert(target="MESH")
    bpy.context.object.name = name
    return bpy.context.object


def add_iso_unit(bpy, mats: dict, index: int, x: float, y: float, assumptions: dict) -> None:
    iso = assumptions["isoContainer"]
    length = iso["length"]
    width = iso["width"]
    height = iso["height"]
    radius = iso["tankRadius"]
    z_base = 0.18
    z_mid = z_base + height * 0.52

    add_cylinder_x(bpy, f"ISO-{index:02d} insulated LNG vessel", (x, y, z_mid), length, radius, mats["iso_tank"], vertices=64)
    add_cylinder_x(bpy, f"ISO-{index:02d} static LNG fill volume", (x, y, z_mid - 0.18), length * 0.94, radius * 0.82, mats["lng"], vertices=48)

    rail_z_low = z_base + 0.15
    rail_z_high = z_base + height - 0.12
    for side_y in (y - width / 2, y + width / 2):
        add_cube(bpy, f"ISO-{index:02d} side rail lower", (x, side_y, rail_z_low), (length, 0.08, 0.08), mats["iso_frame"])
        add_cube(bpy, f"ISO-{index:02d} side rail upper", (x, side_y, rail_z_high), (length, 0.08, 0.08), mats["iso_frame"])
    for end_x in (x - length / 2, x + length / 2):
        for side_y in (y - width / 2, y + width / 2):
            add_cube(bpy, f"ISO-{index:02d} corner post", (end_x, side_y, z_base + height / 2), (0.12, 0.12, height), mats["iso_frame"])

    add_cube(bpy, f"ISO-{index:02d} valve cabinet", (x + length * 0.38, y - width * 0.58, z_base + 1.0), (0.75, 0.16, 0.72), mats["apollo_navy"])


def add_trailer_tank(bpy, mats: dict, name: str, x: float, y: float, dims: dict) -> None:
    length = dims["length"]
    width = dims["width"]
    add_cube(bpy, f"{name} trailer frame", (x, y, 0.55), (length, width, 0.35), mats["skid"])
    add_cylinder_x(bpy, f"{name} pressure vessel", (x, y, 2.15), length * 0.88, 1.18, mats["iso_tank"], vertices=64)
    add_cube(bpy, f"{name} controls cabinet", (x + length * 0.34, y - width * 0.55, 1.35), (1.1, 0.2, 1.0), mats["apollo_navy"])
    add_cylinder_z(bpy, f"{name} wheel set A", (x - length * 0.32, y - width * 0.56, 0.42), 0.16, 0.42, mats["road"], vertices=32)
    add_cylinder_z(bpy, f"{name} wheel set B", (x + length * 0.32, y - width * 0.56, 0.42), 0.16, 0.42, mats["road"], vertices=32)


def add_equipment_skid(bpy, mats: dict, name: str, x: float, y: float, dims: tuple[float, float, float], label: str) -> None:
    length, width, height = dims
    add_cube(bpy, f"{name} base", (x, y, 0.25), (length, width, 0.5), mats["skid"])
    add_cube(bpy, f"{name} package enclosure", (x, y, 0.55 + height / 2), (length * 0.82, width * 0.72, height), mats["apollo_navy"])
    add_cube(bpy, f"{name} service clearance", (x, y, 0.04), (length + 1.8, width + 1.4, 0.04), mats["apollo_gold"])
    add_label(bpy, f"{name} label", label, (x, y, 0.09), 0.9, mats["label"])


def build_scene(bpy, Vector, payload: dict, option: dict, out_dir: Path) -> tuple[Path, Path]:
    clear_scene(bpy)
    mats = make_materials(bpy)
    assumptions = payload["assumptions"]
    metrics = layout_metrics(payload, option)
    site_length = metrics["siteLength"]
    site_width = metrics["siteWidth"]
    iso = assumptions["isoContainer"]
    spacing = assumptions["isoSpacing"]

    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.cycles.samples = 96
    bpy.context.scene.view_settings.view_transform = "Filmic"
    bpy.context.scene.world.color = (0.78, 0.82, 0.86)

    add_cube(bpy, "Draft engineering concrete site pad", (0, 0, -0.05), (site_length, site_width, 0.1), mats["pad"])
    add_cube(bpy, "Access road and turning apron", (-site_length * 0.12, site_width / 2 + 6.5, 0.01), (site_length * 0.86, 8.0, 0.08), mats["road"])

    fence_z = 1.1
    add_pipe(bpy, "Security fence north", [(-site_length / 2, site_width / 2, fence_z), (site_length / 2, site_width / 2, fence_z)], 0.045, mats["fence"])
    add_pipe(bpy, "Security fence south", [(-site_length / 2, -site_width / 2, fence_z), (site_length / 2, -site_width / 2, fence_z)], 0.045, mats["fence"])
    add_pipe(bpy, "Security fence east", [(site_length / 2, -site_width / 2, fence_z), (site_length / 2, site_width / 2, fence_z)], 0.045, mats["fence"])
    add_pipe(bpy, "Security fence west", [(-site_length / 2, -site_width / 2, fence_z), (-site_length / 2, site_width / 2, fence_z)], 0.045, mats["fence"])
    for x in [(-site_length / 2) + i * 10.0 for i in range(max(2, int(site_length / 10.0) + 1))]:
        add_cylinder_z(bpy, "Fence post", (x, site_width / 2, 0.55), 1.1, 0.045, mats["fence"], vertices=12)
        add_cylinder_z(bpy, "Fence post", (x, -site_width / 2, 0.55), 1.1, 0.045, mats["fence"], vertices=12)

    array_length = metrics["arrayLength"]
    array_width = metrics["arrayWidth"]
    array_center_x = -site_length * 0.10
    array_center_y = -2.0
    start_x = array_center_x - array_length / 2
    start_y = array_center_y - array_width / 2
    index = 1
    for row in range(option["isoRows"]):
        for col in range(option["isoCols"]):
            if index > option["isoCount"]:
                break
            x = start_x + col * spacing["x"] + iso["length"] / 2
            y = start_y + row * spacing["y"] + iso["width"] / 2
            add_iso_unit(bpy, mats, index, x, y, assumptions)
            index += 1

    header_y = array_center_y - array_width / 2 - 4.0
    add_pipe(bpy, "Common cryogenic ISO manifold", [(start_x - 2, header_y, 1.0), (start_x + array_length + 2, header_y, 1.0)], 0.12, mats["cryo"])
    for col in range(option["isoCols"]):
        x = start_x + col * spacing["x"] + iso["length"] / 2
        add_pipe(bpy, "ISO branch header", [(x, header_y, 1.0), (x, header_y + 3.0, 1.0)], 0.055, mats["cryo"])

    queen_x = -site_length / 2 + 28.0
    queen_y = -site_width / 2 + 12.0
    add_trailer_tank(bpy, mats, "HP Smart Queen 1", queen_x, queen_y, assumptions["queenTrailer"])
    add_trailer_tank(bpy, mats, "HP Smart Queen 2", queen_x + 16.5, queen_y, assumptions["queenTrailer"])
    add_label(bpy, "Queens label", "2x HP SMART QUEENS", (queen_x + 8.2, queen_y - 4.2, 0.09), 0.9, mats["label"])

    truck_x = -site_length / 2 + 27.0
    truck_y = site_width / 2 - 13.5
    add_cube(bpy, "Transport offload bay pavement", (truck_x, truck_y, 0.03), (assumptions["truckBay"]["length"], assumptions["truckBay"]["width"], 0.06), mats["road"])
    add_trailer_tank(bpy, mats, "LNG transport offload", truck_x, truck_y, {"length": 18.0, "width": 2.55, "height": 3.3})
    add_label(bpy, "Truck bay label", "TRANSPORT OFFLOAD BAY", (truck_x, truck_y + 4.4, 0.09), 0.85, mats["label"])

    equip_x = site_length / 2 - 35.0
    vaporizer_y = -6.0
    add_equipment_skid(
        bpy,
        mats,
        "Vaporizer skid",
        equip_x,
        vaporizer_y,
        (
            assumptions["vaporizerSkid"]["length"],
            assumptions["vaporizerSkid"]["width"],
            assumptions["vaporizerSkid"]["height"],
        ),
        "GLYCOL-BATH HP VAPORIZER",
    )
    add_cylinder_z(bpy, "Vaporizer stack", (equip_x + 3.2, vaporizer_y + 1.9, 5.0), 3.8, 0.36, mats["skid"], vertices=32)

    pump_target = (equip_x - 13.0, vaporizer_y - 9.0, 1.0)
    if option.get("hasPump"):
        add_equipment_skid(
            bpy,
            mats,
            "Pad pump skid",
            pump_target[0],
            pump_target[1],
            (
                assumptions["pumpSkid"]["length"],
                assumptions["pumpSkid"]["width"],
                assumptions["pumpSkid"]["height"],
            ),
            "PAD TRANSFER PUMP",
        )

    if option.get("hasCapture"):
        bog_x = equip_x - 13.0
        bog_y = vaporizer_y - 9.0
        add_equipment_skid(
            bpy,
            mats,
            "BOG capture skid",
            bog_x,
            bog_y,
            (
                assumptions["bogSkid"]["length"],
                assumptions["bogSkid"]["width"],
                assumptions["bogSkid"]["height"],
            ),
            "BOG CAPTURE SKID",
        )

    delivery_x = site_length / 2 - 7.0
    delivery_y = vaporizer_y + 2.5
    add_cylinder_z(bpy, "Delivery flange riser", (delivery_x, delivery_y, 1.1), 2.2, 0.32, mats["warm"], vertices=40)
    add_label(bpy, "Delivery flange label", "DELIVERY FLANGE 550-650 PSIG", (delivery_x - 4.7, delivery_y + 3.2, 0.09), 0.75, mats["label"])

    header_end_x = start_x + array_length + 2
    process_x = pump_target[0] if option.get("hasPump") or option.get("hasCapture") else equip_x - 11.0
    process_y = pump_target[1]
    add_pipe(bpy, "Truck offload to ISO header", [(truck_x + 7.5, truck_y - 3.2, 1.0), (truck_x + 7.5, header_y, 1.0), (start_x - 2, header_y, 1.0)], 0.10, mats["cryo"])
    add_pipe(bpy, "ISO header to process skid", [(header_end_x, header_y, 1.0), (process_x, header_y, 1.0), (process_x, process_y, 1.0)], 0.12, mats["cryo"])
    add_pipe(bpy, "Process skid to vaporizer", [(process_x, process_y, 1.0), (equip_x - 6.2, process_y, 1.0), (equip_x - 6.2, vaporizer_y, 1.0)], 0.12, mats["cryo"])
    add_pipe(bpy, "Queens HP feed to vaporizer", [(queen_x + 16.0, queen_y + 3.0, 1.2), (equip_x - 7.0, queen_y + 3.0, 1.2), (equip_x - 7.0, vaporizer_y - 2.4, 1.2)], 0.09, mats["cryo"])
    add_pipe(bpy, "Warm gas route to delivery", [(equip_x + 5.4, vaporizer_y + 2.2, 1.4), (delivery_x, vaporizer_y + 2.2, 1.4), (delivery_x, delivery_y, 1.4)], 0.14, mats["warm"])

    add_label(bpy, "Array label", f"{option['isoCount']}x 10k LNG ISO ARRAY", (array_center_x, array_center_y + array_width / 2 + 5.4, 0.09), 1.0, mats["label"])
    add_label(bpy, "Model title label", f"APOLLO LNG OPTION {option['letter']} - DRAFT ENGINEERING GEOMETRY", (0, -site_width / 2 + 3.0, 0.09), 1.1, mats["apollo_navy"])
    add_label(bpy, "Fidelity label", "PENDING VENDOR CAD REPLACEMENT", (0, -site_width / 2 + 5.2, 0.09), 0.75, mats["label"])

    bpy.ops.object.light_add(type="SUN", location=(0, 0, 30))
    sun = bpy.context.object
    sun.name = "Sun - engineering review"
    sun.data.energy = 2.0
    sun.rotation_euler = (math.radians(42), 0, math.radians(32))

    bpy.ops.object.light_add(type="AREA", location=(0, -site_width * 0.4, 34))
    area = bpy.context.object
    area.name = "Large softbox"
    area.data.energy = 650.0
    area.data.size = 48.0

    bpy.ops.object.camera_add(location=(site_length * 0.35, -site_width * 1.05, max(site_length, site_width) * 0.52))
    camera = bpy.context.object
    target = Vector((0, 0, 1.0))
    direction = target - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 28
    camera.data.dof.use_dof = False
    bpy.context.scene.camera = camera

    out_dir.mkdir(parents=True, exist_ok=True)
    slug = option_slug(option)
    blend_path = out_dir / f"{slug}.blend"
    glb_path = out_dir / f"{slug}.glb"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.export_scene.gltf(filepath=str(glb_path), export_format="GLB", export_yup=True)
    return blend_path, glb_path


def build_from_site(args, site) -> None:
    """New entry point that consumes a Site dataclass from site_config.load_site().

    Reproduces site-level scenery (pad, fence, access road, lights, camera, labels)
    from build_scene(), then dispatches per-equipment builders via BUILDERS registry.

    Intentionally NOT reproduced (delta vs build_scene):
      - Inter-equipment piping (truck->header, header->process, process->vaporizer,
        queens HP feed, warm gas to delivery). These are inter-equipment runs that
        need anchor positions; deferred per Task 7 note (Concern #2, option b).
      - pump skid (legacy "hasPump" branch). Equipment list in YAML drives this now.
    """
    bpy, Vector = import_bpy()
    sys.path.insert(0, str(project_root() / "scripts"))
    from lib.equipment_builders import BUILDERS  # pyright: ignore[reportMissingImports]

    payload = json.loads((project_root() / args.data).read_text())
    assumptions = payload["assumptions"]
    out_dir = resolve_path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    clear_scene(bpy)
    mats = make_materials(bpy)

    # Scene-wide settings (parity with build_scene lines 302-306).
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.cycles.samples = 96
    bpy.context.scene.view_settings.view_transform = "Filmic"
    bpy.context.scene.world.color = (0.78, 0.82, 0.86)

    # Derive site_length / site_width the same way build_scene does (lines 87-102).
    iso_dim = assumptions["isoContainer"]
    spacing = assumptions["isoSpacing"]
    array_length = iso_dim["length"] + (site.iso_array.cols - 1) * spacing["x"]
    array_width = iso_dim["width"] + (site.iso_array.rows - 1) * spacing["y"]
    footprint_area = site.footprintAcres * 4046.8564224
    site_length = max(array_length + 70.0, math.sqrt(footprint_area * 1.7))
    site_width = max(array_width + 45.0, footprint_area / site_length)

    # Site pad + access road (parity with build_scene lines 308-309).
    add_cube(bpy, "Draft engineering concrete site pad", (0, 0, -0.05),
             (site_length, site_width, 0.1), mats["pad"])
    add_cube(bpy, "Access road and turning apron",
             (-site_length * 0.12, site_width / 2 + 6.5, 0.01),
             (site_length * 0.86, 8.0, 0.08), mats["road"])

    # Security fence (parity with build_scene lines 311-318).
    fence_z = 1.1
    add_pipe(bpy, "Security fence north",
             [(-site_length / 2, site_width / 2, fence_z),
              (site_length / 2, site_width / 2, fence_z)], 0.045, mats["fence"])
    add_pipe(bpy, "Security fence south",
             [(-site_length / 2, -site_width / 2, fence_z),
              (site_length / 2, -site_width / 2, fence_z)], 0.045, mats["fence"])
    add_pipe(bpy, "Security fence east",
             [(site_length / 2, -site_width / 2, fence_z),
              (site_length / 2, site_width / 2, fence_z)], 0.045, mats["fence"])
    add_pipe(bpy, "Security fence west",
             [(-site_length / 2, -site_width / 2, fence_z),
              (-site_length / 2, site_width / 2, fence_z)], 0.045, mats["fence"])
    for x in [(-site_length / 2) + i * 10.0 for i in range(max(2, int(site_length / 10.0) + 1))]:
        add_cylinder_z(bpy, "Fence post", (x, site_width / 2, 0.55), 1.1, 0.045, mats["fence"], vertices=12)
        add_cylinder_z(bpy, "Fence post", (x, -site_width / 2, 0.55), 1.1, 0.045, mats["fence"], vertices=12)

    # ISO array: dispatch iso_unit builder per cell.
    sx = spacing["x"]
    sy = spacing["y"]
    ox, oy, oz = site.iso_array.origin
    for r in range(site.iso_array.rows):
        for c in range(site.iso_array.cols):
            cell_idx = r * site.iso_array.cols + c
            if cell_idx >= site.iso_array.count:
                break
            # iso_array.origin in YAML points at the centroid of the bottom-left cell
            # (see scaffolder Task 5), so cells live at (ox + c*sx, oy + r*sy).
            cell_pos = (ox + c * sx, oy + r * sy, oz)
            BUILDERS["iso_unit"](bpy, mats, f"iso_{cell_idx:02d}", cell_pos, 0.0, assumptions)

    # Other equipment from YAML.
    for eq in site.equipment:
        BUILDERS[eq.type](bpy, mats, eq.id, eq.pos, eq.rotation, assumptions)

    # Array centroid for labels (parity with build_scene lines 322-323).
    array_center_x = -site_length * 0.10
    array_center_y = -2.0

    # Labels (parity with build_scene lines 418-420).
    add_label(bpy, "Array label", f"{site.iso_array.count}x 10k LNG ISO ARRAY",
              (array_center_x, array_center_y + array_width / 2 + 5.4, 0.09),
              1.0, mats["label"])
    add_label(bpy, "Model title label",
              f"APOLLO LNG OPTION {site.letter} - DRAFT ENGINEERING GEOMETRY",
              (0, -site_width / 2 + 3.0, 0.09), 1.1, mats["apollo_navy"])
    add_label(bpy, "Fidelity label", "PENDING VENDOR CAD REPLACEMENT",
              (0, -site_width / 2 + 5.2, 0.09), 0.75, mats["label"])

    # Lights (parity with build_scene lines 422-432).
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 30))
    sun = bpy.context.object
    sun.name = "Sun - engineering review"
    sun.data.energy = 2.0
    sun.rotation_euler = (math.radians(42), 0, math.radians(32))

    bpy.ops.object.light_add(type="AREA", location=(0, -site_width * 0.4, 34))
    area = bpy.context.object
    area.name = "Large softbox"
    area.data.energy = 650.0
    area.data.size = 48.0

    # Camera (parity with build_scene lines 434-441).
    bpy.ops.object.camera_add(
        location=(site_length * 0.35, -site_width * 1.05,
                  max(site_length, site_width) * 0.52))
    camera = bpy.context.object
    target = Vector((0, 0, 1.0))
    direction = target - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 28
    camera.data.dof.use_dof = False
    bpy.context.scene.camera = camera

    blend_path = out_dir / f"option-{site.letter.lower()}.blend"
    glb_path = out_dir / f"option-{site.letter.lower()}.glb"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.export_scene.gltf(filepath=str(glb_path), export_format="GLB", export_yup=True)
    print(f"[generator] wrote {blend_path} and {glb_path}")


def main() -> None:
    args = parse_args(sys.argv)

    if args.site:
        sys.path.insert(0, str(project_root() / "scripts"))
        from lib.site_config import load_site  # pyright: ignore[reportMissingImports]
        site = load_site(args.site)
        return build_from_site(args, site)

    payload = load_payload(args.data)
    options = selected_options(payload, args)

    if args.dry_run:
        summaries = [dry_run_summary(payload, option, args.out) for option in options]
        print(json.dumps(summaries[0] if len(summaries) == 1 else summaries, indent=2))
        return

    bpy, Vector = import_bpy()
    out_dir = resolve_path(args.out)
    generated = []
    for option in options:
        blend_path, glb_path = build_scene(bpy, Vector, payload, option, out_dir)
        generated.append({"option": option["letter"], "blend": str(blend_path), "glb": str(glb_path)})
    print(json.dumps(generated, indent=2))


if __name__ == "__main__":
    main()
