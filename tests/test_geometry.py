import math
import unittest

from screen_overlay.geometry import Placement


class GeometryTests(unittest.TestCase):
    def test_scaling_endpoints_never_escape_limits_due_to_rounding(self):
        for width, height in ((47, 100), (100, 47), (143, 257), (257, 143)):
            p = Placement(0, 0, width, height, 37)
            for factor in (0.00001, 1e6):
                q = p.zoom_at(factor, 10, 20)
                self.assertTrue(24 <= q.width <= 16384)
                self.assertTrue(24 <= q.height <= 16384)
                self.assertAlmostEqual(q.width / q.height, p.width / p.height)
            for size in (24, 16384):
                self.assertIsInstance(p.with_width(size, True), Placement)
                self.assertIsInstance(p.with_height(size, True), Placement)
            for x, y in ((-10000, -10000), (1e6, 1e6)):
                q = p.resized("se", x, y, True)
                self.assertTrue(24 <= q.width <= 16384)
                self.assertTrue(24 <= q.height <= 16384)

    def test_rotated_coordinates_roundtrip(self):
        p = Placement(-500, 250, 300, 150, 37)
        x, y = p.local_to_world(80, -44)
        a, b = p.world_to_local(x, y)
        self.assertAlmostEqual(a, 80)
        self.assertAlmostEqual(b, -44)

    def test_zoom_preserves_point_under_cursor(self):
        p = Placement(-200, 500, 300, 150, 72)
        anchor = (-90, 460)
        old = p.world_to_local(*anchor)
        q = p.zoom_at(2, *anchor)
        new = q.world_to_local(*anchor)
        self.assertAlmostEqual(old[0] / p.width, new[0] / q.width)
        self.assertAlmostEqual(old[1] / p.height, new[1] / q.height)

    def test_zoom_clamps_both_dimensions_together(self):
        q = Placement(0, 0, 16000, 100).zoom_at(100, 0, 0)
        self.assertEqual(q.width, 16384)
        self.assertAlmostEqual(q.width / q.height, 160)
        self.assertGreaterEqual(q.height, 24)

    def test_resize_rotated_keeps_opposite_corner_fixed(self):
        p = Placement(300, 400, 200, 100, 31)
        opposite = p.local_to_world(-100, -50)
        target = p.local_to_world(200, 100)
        q = p.resized("se", *target, keep_aspect=True)
        fixed = q.local_to_world(-q.width / 2, -q.height / 2)
        self.assertAlmostEqual(fixed[0], opposite[0])
        self.assertAlmostEqual(fixed[1], opposite[1])
        self.assertAlmostEqual(q.width / q.height, 2)
        self.assertAlmostEqual(q.width, 300)

    def test_free_resize_changes_width_without_height(self):
        p = Placement(0, 0, 200, 100)
        q = p.resized("e", 300, 90, keep_aspect=False)
        self.assertEqual(q.width, 400)
        self.assertEqual(q.height, 100)
        self.assertEqual(q.center_x, 100)

    def test_resize_cannot_cross_opposite_edge(self):
        p = Placement(0, 0, 200, 100)
        q = p.resized("e", -1000, 0, keep_aspect=False)
        self.assertEqual(q.width, 24)
        self.assertEqual(q.center_x - q.width / 2, -100)

    def test_independent_dimension_then_aspect_locked_dimension(self):
        p = Placement(0, 0, 200, 100)
        self.assertEqual(p.with_size(400, 80).height, 80)
        q = p.with_width(400, keep_aspect=True)
        self.assertEqual(q.height, 200)

    def test_fit_preserves_ratio_and_negative_monitor_origin(self):
        q = Placement.fit(4000, 1000, (-1920, 0, 1920, 1080))
        self.assertAlmostEqual(q.width / q.height, 4)
        self.assertEqual(q.center_x, -960)
        self.assertEqual(q.center_y, 540)
        self.assertLessEqual(q.width, 1920 * 0.8)

    def test_tiny_image_is_enlarged_without_distortion(self):
        q = Placement.fit(8, 20, (0, 0, 1920, 1080))
        self.assertAlmostEqual(q.width / q.height, 8 / 20)

    def test_impossibly_thin_image_is_rejected_instead_of_distorted(self):
        with self.assertRaises(ValueError):
            Placement.fit(16384, 1, (0, 0, 1920, 1080))

    def test_rejects_nonfinite_and_invalid_dimensions(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.assertRaises(ValueError):
                Placement(value, 0, 100, 100)
        with self.assertRaises(ValueError):
            Placement(0, 0, 0, 100)
        with self.assertRaises(ValueError):
            Placement(0, 0, 100, 100).zoom_at(float("nan"), 0, 0)

    def test_all_eight_handles_anchor_opposite_side(self):
        p = Placement(100, 200, 200, 100, 50)
        for h in ("n", "ne", "e", "se", "s", "sw", "w", "nw"):
            sx = 1 if "e" in h else -1 if "w" in h else 0
            sy = 1 if "s" in h else -1 if "n" in h else 0
            target = p.local_to_world(sx * 160, sy * 80)
            q = p.resized(h, *target, keep_aspect=True)
            before = p.local_to_world(-sx * p.width / 2, -sy * p.height / 2)
            after = q.local_to_world(-sx * q.width / 2, -sy * q.height / 2)
            self.assertAlmostEqual(before[0], after[0], msg=h)
            self.assertAlmostEqual(before[1], after[1], msg=h)


if __name__ == "__main__":
    unittest.main()
