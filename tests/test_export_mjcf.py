from __future__ import annotations

import unittest
from types import SimpleNamespace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kiln.envio.export import KILN_NS, _build_mjcf
from kiln.objects import Box, Plane


class TestMjcfExport(unittest.TestCase):
    def test_actor_and_npc_export_tags(self) -> None:
        car = Box("car")
        car.role = "car"
        car.control_mode = "kinematic"
        car.max_speed = 5.0
        car.speed_delta = 0.5
        car.turn_rate = 1.5
        car.force = 30.0
        car.torque = 10.0
        car.initial_yaw = 0.0

        npc = Box("npc_0")
        npc.role = "npc"
        npc.control_mode = "kinematic"
        npc.max_speed = 6.0
        npc.speed_delta = 1.0
        npc.turn_rate = 3.0
        npc.force = 30.0
        npc.torque = 10.0
        npc.initial_yaw = 0.0
        npc.roam_xy_min = (-12.0, -12.0)
        npc.roam_xy_max = (12.0, 12.0)
        npc.goal_tolerance = 0.5
        npc.cruise_speed = 4.0
        npc.heading_threshold = 0.25
        npc.raycast_length = 2.0
        npc.raycast_angle = 0.45
        npc.avoid_distance = 1.25
        npc.brake_distance = 0.5
        npc.avoid_radius = 1.0
        npc.emergency_brake_radius = 0.6
        npc.stuck_steps = 30
        npc.progress_eps = 0.001
        npc.nav_cell_size = 0.5
        npc.nav_inflate = 0.55
        npc.waypoint_tolerance = 0.6
        npc.max_goal_samples = 50

        scene = SimpleNamespace(objects=[car, npc])
        root = _build_mjcf(scene, "scene.usda", "test_scene")
        ns = {"kiln": KILN_NS}

        car_body = root.find("./worldbody/body[@name='car']")
        self.assertIsNotNone(car_body)
        assert car_body is not None
        self.assertIsNotNone(car_body.find("freejoint"))
        self.assertIsNone(car_body.find("kiln:primitive", ns))
        car_actor = car_body.find("kiln:actor", ns)
        self.assertIsNotNone(car_actor)
        assert car_actor is not None
        self.assertEqual(car_actor.attrib.get("type"), "car_block")
        self.assertEqual(car_actor.attrib.get("control_mode"), "kinematic")
        self.assertIsNotNone(car_actor.find("kiln:control", ns))
        self.assertIsNotNone(car_actor.find("kiln:action_map", ns))
        self.assertIsNone(car_actor.find("kiln:npc_policy", ns))

        npc_body = root.find("./worldbody/body[@name='npc_0']")
        self.assertIsNotNone(npc_body)
        assert npc_body is not None
        self.assertIsNotNone(npc_body.find("freejoint"))
        self.assertIsNone(npc_body.find("kiln:primitive", ns))
        npc_actor = npc_body.find("kiln:actor", ns)
        self.assertIsNotNone(npc_actor)
        assert npc_actor is not None
        self.assertEqual(npc_actor.attrib.get("type"), "npc_block")
        self.assertEqual(npc_actor.attrib.get("control_mode"), "kinematic")
        self.assertIsNotNone(npc_actor.find("kiln:control", ns))
        npc_policy = npc_actor.find("kiln:npc_policy", ns)
        self.assertIsNotNone(npc_policy)
        assert npc_policy is not None
        self.assertEqual(npc_policy.attrib.get("roam_xy_min"), "-12 -12")
        self.assertEqual(npc_policy.attrib.get("roam_xy_max"), "12 12")
        self.assertEqual(npc_policy.attrib.get("max_goal_samples"), "50")
        self.assertIsNotNone(npc_actor.find("kiln:action_map", ns))

    def test_non_actor_primitives_remain_primitive_tags(self) -> None:
        ground = Plane("ground")
        ground.role = "ground"
        building = Box("building_0")
        building.role = "building"

        scene = SimpleNamespace(objects=[ground, building])
        root = _build_mjcf(scene, "scene.usda", "test_scene")
        ns = {"kiln": KILN_NS}

        ground_body = root.find("./worldbody/body[@name='ground']")
        self.assertIsNotNone(ground_body)
        assert ground_body is not None
        self.assertIsNotNone(ground_body.find("kiln:primitive", ns))
        self.assertIsNone(ground_body.find("kiln:actor", ns))

        building_body = root.find("./worldbody/body[@name='building']")
        self.assertIsNotNone(building_body)
        assert building_body is not None
        self.assertIsNotNone(building_body.find("kiln:primitive", ns))
        self.assertIsNone(building_body.find("kiln:actor", ns))


if __name__ == "__main__":
    unittest.main()
