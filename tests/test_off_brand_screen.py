"""Quick hits and the big number must stay world news: domestic crime,
executions, campus scandals and celebrity fare are dropped after generation."""

import unittest

from src.ai.editorial import is_off_brand


class TestOffBrandMarkers(unittest.TestCase):
    def test_domestic_justice_and_campus_items_flagged(self):
        self.assertEqual(
            is_off_brand("Tennessee's prisons chief resigned after the botched execution of Christa Pike, "
                         "who survived two lethal injection attempts."),
            "botched execution")
        self.assertEqual(
            is_off_brand("Cornell's president called an alleged 2024 fraternity gang rape 'deeply disturbing'."),
            "fraternity")
        self.assertEqual(is_off_brand("Christa Pike, on death row in Tennessee, is in critical condition."),
                         "death row")

    def test_geopolitical_items_untouched(self):
        for text in (
            "Iran executed three men convicted of spying for Israel, rights groups said.",
            "Russia struck Kyiv's Pivnichnyi Bridge; Ukraine plans pontoon crossings.",
            "A Ukrainian drone crashed near a refinery in Kaluga, Moscow says.",
            "The IEA said member countries have released 325 million barrels of emergency oil.",
            "Bosnians voted in elections that could decide their path toward EU membership.",
        ):
            self.assertIsNone(is_off_brand(text), text)


if __name__ == "__main__":
    unittest.main()
