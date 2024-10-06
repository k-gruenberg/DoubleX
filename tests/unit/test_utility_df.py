import unittest

from pdg_js.utility_df import cross_product


class TestUtilityDF(unittest.TestCase):
    def test_cross_product(self):
        xs = [1, 2]
        ys = [3, 4, 5]
        cross_prod = list(cross_product(xs, ys))
        self.assertEqual(cross_prod, [(1, 3), (1, 4), (1, 5), (2, 3), (2, 4), (2, 5)])

        xs = [1, 2, 3]
        ys = [3, 4, 5]
        cross_prod = list(cross_product(xs, ys, where_either_equals=3))
        self.assertEqual(cross_prod, [(3, 3), (3, 4), (3, 5), (1, 3), (2, 3), (3, 3)])

        xs = [i for i in range(500_000)]
        ys = [i for i in range(500_000)]
        cross_prod = list(cross_product(xs, ys, where_either_equals=250_000))
        self.assertEqual(len(cross_prod), 1_000_000)
        # # Note that this code terminates in <100ms, while the following would need MUCH langer:
        # for x in xs:
        #     for y in ys:
        #         if x == 250_000 or y == 250_000:
        #             pass


if __name__ == '__main__':
    unittest.main()
