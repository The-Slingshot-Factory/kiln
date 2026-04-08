from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kiln.envio.bundle import EnvBundleError
from kiln.envio.xml_bundle import load_env_xml_bundle


def _write_xml(tmp: Path, content: str) -> Path:
    xml_path = tmp / "scene.xml"
    xml_path.write_text(content, encoding="utf-8")
    return xml_path


class TestXmlBundleActors(unittest.TestCase):
    def test_parses_car_and_npc_actor_specs(self) -> None:
        xml = """<?xml version='1.0' encoding='utf-8'?>
<mujoco xmlns:kiln="urn:kiln:mjcf:v1" model="actors" kiln:schema_version="1">
  <worldbody>
    <body name="building" pos="0 0 0" quat="1 0 0 0">
      <geom name="building_geom" type="box" size="1 1 1" mass="0" />
      <kiln:primitive id="building" shape="box" fixed="true" />
    </body>
    <body name="car_0" pos="2 0 0.15" quat="1 0 0 0">
      <geom name="car_geom" type="box" size="0.5 0.25 0.15" mass="1.0" rgba="1 0 0 1" />
      <freejoint />
      <kiln:actor type="car_block" control_mode="kinematic">
        <kiln:control max_speed="5" speed_delta="0.5" turn_rate="1.5" force="30" torque="10" initial_yaw="0" />
        <kiln:action_map accelerate="0" decelerate="1" turn_left="2" turn_right="3" />
      </kiln:actor>
    </body>
    <body name="npc_0" pos="-2 0 0.15" quat="1 0 0 0">
      <geom name="npc_geom" type="box" size="0.125 0.125 0.25" mass="1.0" rgba="0 0 1 1" />
      <freejoint />
      <kiln:actor type="npc_block" control_mode="kinematic">
        <kiln:control max_speed="6" speed_delta="1" turn_rate="3" force="30" torque="10" initial_yaw="0" />
        <kiln:npc_policy roam_xy_min="-12 -12" roam_xy_max="12 12" goal_tolerance="0.5"
                         cruise_speed="4" heading_threshold="0.25" raycast_length="2" raycast_angle="0.45"
                         avoid_distance="1.25" brake_distance="0.5" avoid_radius="1" emergency_brake_radius="0.6"
                         stuck_steps="30" progress_eps="0.001" nav_cell_size="0.5" nav_inflate="0.55"
                         waypoint_tolerance="0.6" max_goal_samples="50" />
        <kiln:action_map accelerate="0" decelerate="1" turn_left="2" turn_right="3" />
      </kiln:actor>
    </body>
  </worldbody>
  <kiln:spawn_points>
    <kiln:spawn name="default" pos="0 0 1.2" quat="1 0 0 0" />
  </kiln:spawn_points>
</mujoco>
"""
        with tempfile.TemporaryDirectory() as td:
            xml_path = _write_xml(Path(td), xml)
            bundle = load_env_xml_bundle(xml_path)

        self.assertEqual([p.id for p in bundle.primitives], ["building"])
        actors = list(getattr(bundle, "actors", ()))
        self.assertEqual(len(actors), 2)

        car = next(a for a in actors if a.id == "car_0")
        self.assertEqual(car.actor_type, "car_block")
        self.assertEqual(car.control_mode, "kinematic")
        self.assertEqual(car.action_map, (0, 1, 2, 3))
        self.assertEqual(car.size, (1.0, 0.5, 0.3))

        npc = next(a for a in actors if a.id == "npc_0")
        self.assertEqual(npc.actor_type, "npc_block")
        self.assertEqual(npc.roam_xy_min, (-12.0, -12.0))
        self.assertEqual(npc.roam_xy_max, (12.0, 12.0))
        self.assertAlmostEqual(npc.nav_inflate, 0.55)
        self.assertEqual(npc.max_goal_samples, 50)

    def test_rejects_invalid_actor_control_mode(self) -> None:
        xml = """<?xml version='1.0' encoding='utf-8'?>
<mujoco xmlns:kiln="urn:kiln:mjcf:v1" model="actors" kiln:schema_version="1">
  <worldbody>
    <body name="car_0" pos="0 0 0.15" quat="1 0 0 0">
      <geom name="car_geom" type="box" size="0.5 0.25 0.15" mass="1.0" />
      <kiln:actor type="car_block" control_mode="invalid_mode" />
    </body>
  </worldbody>
</mujoco>
"""
        with tempfile.TemporaryDirectory() as td:
            xml_path = _write_xml(Path(td), xml)
            with self.assertRaises(EnvBundleError):
                load_env_xml_bundle(xml_path)

    def test_converts_y_up_coordinates_to_z_up(self) -> None:
        xml = """<?xml version='1.0' encoding='utf-8'?>
<mujoco xmlns:kiln="urn:kiln:mjcf:v1" model="axis_convert" kiln:schema_version="1" kiln:up_axis="y">
  <asset>
    <mesh name="world_mesh" file="scene.usda" />
  </asset>
  <worldbody>
    <body name="world" pos="1 2 3" quat="1 0 0 0">
      <geom name="world_geom" type="mesh" mesh="world_mesh" mass="0" />
      <kiln:world source_file="scene.usda" fixed="true" collision="true" visualization="true" scale="1.0" />
    </body>
    <body name="ground" pos="0 2 0" quat="1 0 0 0">
      <geom name="ground_geom" type="plane" size="10 10 1" mass="0" />
      <kiln:primitive id="ground" shape="plane" normal="0 1 0" fixed="true" />
    </body>
    <body name="car_0" pos="4 5 6" quat="1 0 0 0">
      <geom name="car_geom" type="box" size="0.5 0.5 0.5" mass="1.0" />
      <kiln:actor type="car_block" control_mode="kinematic" />
    </body>
  </worldbody>
  <kiln:spawn_points>
    <kiln:spawn name="default" pos="7 8 9" quat="1 0 0 0" />
  </kiln:spawn_points>
</mujoco>
"""
        with tempfile.TemporaryDirectory() as td:
            xml_path = _write_xml(Path(td), xml)
            bundle = load_env_xml_bundle(xml_path)

        # y-up -> z-up position conversion: (x, y, z) -> (x, -z, y)
        self.assertEqual(bundle.world.pose.pos, (1.0, -3.0, 2.0))

        ground = next(p for p in bundle.primitives if p.id == "ground")
        self.assertEqual(ground.pose.pos, (0.0, 0.0, 2.0))
        self.assertEqual(ground.normal, (0.0, 0.0, 1.0))

        actors = list(getattr(bundle, "actors", ()))
        car = next(a for a in actors if a.id == "car_0")
        self.assertEqual(car.pose.pos, (4.0, -6.0, 5.0))

        spawn = bundle.spawn_points["default"]
        self.assertEqual(spawn.pos, (7.0, -9.0, 8.0))

        # identity source quat should become +90deg around X
        sqrt_half = math.sqrt(0.5)
        self.assertAlmostEqual(bundle.world.pose.quat[0], sqrt_half)
        self.assertAlmostEqual(bundle.world.pose.quat[1], sqrt_half)
        self.assertAlmostEqual(bundle.world.pose.quat[2], 0.0)
        self.assertAlmostEqual(bundle.world.pose.quat[3], 0.0)

    def test_rejects_unsupported_up_axis(self) -> None:
        xml = """<?xml version='1.0' encoding='utf-8'?>
<mujoco xmlns:kiln="urn:kiln:mjcf:v1" model="bad_axis" kiln:schema_version="1" kiln:up_axis="x">
  <worldbody>
    <body name="ground" pos="0 0 0" quat="1 0 0 0">
      <geom name="ground_geom" type="plane" size="10 10 1" mass="0" />
      <kiln:primitive id="ground" shape="plane" normal="0 0 1" />
    </body>
  </worldbody>
</mujoco>
"""
        with tempfile.TemporaryDirectory() as td:
            xml_path = _write_xml(Path(td), xml)
            with self.assertRaises(EnvBundleError):
                load_env_xml_bundle(xml_path)


if __name__ == "__main__":
    unittest.main()

