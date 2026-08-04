import unittest

from scraper import extract_salary_info, should_flag_duration


class ScraperUtilityTests(unittest.TestCase):
    def test_extract_salary_info_handles_nested_values(self):
        job = {
            "salary": [
                {"minimum": "5000", "maximum": "8000"}
            ]
        }
        self.assertEqual(extract_salary_info(job), (5000.0, 8000.0))

    def test_extract_salary_info_handles_dict_values(self):
        job = {
            "salary": {"minimum": "6000", "maximum": "9000"}
        }
        self.assertEqual(extract_salary_info(job), (6000.0, 9000.0))

    def test_extract_salary_info_handles_missing_values(self):
        job = {"salary": None}
        self.assertEqual(extract_salary_info(job), (None, None))

    def test_should_flag_duration_for_fcf_window(self):
        self.assertTrue(should_flag_duration(13))
        self.assertTrue(should_flag_duration(14))
        self.assertTrue(should_flag_duration(15))
        self.assertFalse(should_flag_duration(12))
        self.assertFalse(should_flag_duration(16))


if __name__ == "__main__":
    unittest.main()
