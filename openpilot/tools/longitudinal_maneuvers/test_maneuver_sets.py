import unittest

from openpilot.tools.longitudinal_maneuvers.maneuversd import MANEUVER_SETS, MANEUVERS


class TestManeuverSets(unittest.TestCase):
  def test_stock_set_unchanged(self):
    self.assertIs(MANEUVER_SETS["stock"], MANEUVERS)
    self.assertEqual(len(MANEUVERS), 7)

  def test_maneuvers_within_limits(self):
    for name, maneuvers in MANEUVER_SETS.items():
      for maneuver in maneuvers:
        with self.subTest(set=name, maneuver=maneuver.description):
          self.assertTrue(0. <= maneuver.initial_speed <= 30.)
          for action in maneuver.actions:
            self.assertTrue(all(-3.5 <= a <= 2. for a in action.accel_bp))
            self.assertTrue(all(t > 0. for t in action.time_bp))

  def test_subaru_set_ordered_by_speed(self):
    speeds = [m.initial_speed for m in MANEUVER_SETS["subaru_highway"]]
    self.assertEqual(speeds, sorted(speeds))


if __name__ == "__main__":
  unittest.main()
