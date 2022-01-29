import json
import os
import tempfile
import unittest
from unittest.mock import patch

from waterfalls import Viewer, viewer


class TestViewer(unittest.TestCase):
    """
    Tests the `waterfalls.Viewer` module.
    """

    def test_detect_overlap(self) -> None:
        """
        Tests detecting overlap of timing blocks.
        """
        # Blocks do not overlap
        blocks = [{"start_time": 25, "stop_time": 31}, {"start_time": 35, "stop_time": 42}]
        self.assertFalse(Viewer._detect_overlap(blocks))

        # Blocks touch
        blocks = [{"start_time": 25, "stop_time": 31}, {"start_time": 31, "stop_time": 42}]
        self.assertFalse(Viewer._detect_overlap(blocks))

        # Blocks overlap
        blocks = [{"start_time": 25, "stop_time": 31}, {"start_time": 30, "stop_time": 42}]
        self.assertTrue(Viewer._detect_overlap(blocks))

    def test_load_blocks_from_reports(self) -> None:
        """
        Tests loading timing blocks from report files.
        """
        report_a = [
            {"name": "Timer A", "text": "Block A", "start_time": 25, "stop_time": 35, "thread_id": 100},
            {"name": "Timer B", "text": "Block B", "start_time": 45, "stop_time": 55, "thread_id": 101},
        ]
        report_b = [
            {"name": "Timer C", "text": "Block C", "start_time": 40, "stop_time": 50, "thread_id": 100},
            {"name": "Timer A", "text": "Block D", "start_time": 33, "stop_time": 43, "thread_id": 101},
        ]

        with tempfile.TemporaryDirectory() as temp_dir_name:
            with open(os.path.join(temp_dir_name, "waterfalls.json"), "w") as f:
                json.dump(report_a, f)
            with open(os.path.join(temp_dir_name, "waterfalls.1.json"), "w") as f:
                json.dump(report_b, f)

            viewer_instance = Viewer(directory=temp_dir_name)

            report_file_paths = viewer_instance._get_report_file_paths()
            self.assertEqual(len(report_file_paths), 2)

            blocks = viewer_instance._load_blocks_from_reports(report_file_paths)
            expected_blocks = [
                {
                    "name": "Timer A",
                    "text": "Block A",
                    "start_time": 25,
                    "stop_time": 35,
                    "thread_id": 100,
                },
                {
                    "name": "Timer B",
                    "text": "Block B",
                    "start_time": 45,
                    "stop_time": 55,
                    "thread_id": 101,
                },
                {
                    "name": "Timer C",
                    "text": "Block C",
                    "start_time": 40,
                    "stop_time": 50,
                    "thread_id": 100,
                },
                {
                    "name": "Timer A",
                    "text": "Block D",
                    "start_time": 33,
                    "stop_time": 43,
                    "thread_id": 101,
                },
            ]
            self.assertCountEqual(blocks, expected_blocks)

    def test_group_blocks_to_timers(self) -> None:
        """
        Tests grouping of timing blocks into named timers.
        """
        viewer_instance = Viewer()
        blocks = [
            {
                "name": "Timer A",
                "start_time": 25,
                "stop_time": 35,
            },
            {
                "name": "Timer B",
                "start_time": 45,
                "stop_time": 55,
            },
            {
                "name": "Timer C",
                "start_time": 40,
                "stop_time": 50,
            },
            {
                "name": "Timer A",
                "start_time": 33,
                "stop_time": 43,
            },
        ]

        timers, time_total, time_min = viewer_instance._group_blocks_to_timers(blocks)
        expected_timers = {
            "Timer A": [
                {
                    "name": "Timer A",
                    "start_time": 25,
                    "stop_time": 35,
                },
                {
                    "name": "Timer A",
                    "start_time": 33,
                    "stop_time": 43,
                },
            ],
            "Timer B": [
                {
                    "name": "Timer B",
                    "start_time": 45,
                    "stop_time": 55,
                }
            ],
            "Timer C": [
                {
                    "name": "Timer C",
                    "start_time": 40,
                    "stop_time": 50,
                }
            ],
        }
        self.assertCountEqual(timers, expected_timers)
        self.assertEqual(time_total, 30)
        self.assertEqual(time_min, 25)

    def test_format_timers_names(self) -> None:
        """
        Tests formatting of timers' names depending on whether `show_thead_id` is enabled or disabled.
        """
        viewer_instance = Viewer()
        timers = {
            "Timer A": [
                {
                    "name": "Timer A",
                    "start_time": 25,
                    "stop_time": 35,
                    "thread_id": 100,
                },
                {
                    "name": "Timer A",
                    "start_time": 33,
                    "stop_time": 43,
                    "thread_id": 101,
                },
            ],
            "Timer B": [
                {
                    "name": "Timer B",
                    "start_time": 45,
                    "stop_time": 55,
                    "thread_id": 101,
                }
            ],
            "Timer C": [
                {
                    "name": "Timer C",
                    "start_time": 40,
                    "stop_time": 50,
                    "thread_id": 100,
                }
            ],
        }

        formatted_timers = viewer_instance._format_timer_names(timers)
        expected_formatted_timers = {
            "Timer A\nthread: 100": [
                {
                    "name": "Timer A",
                    "start_time": 25,
                    "stop_time": 35,
                    "thread_id": 100,
                }
            ],
            "Timer A\nthread: 101": [
                {
                    "name": "Timer A",
                    "start_time": 33,
                    "stop_time": 43,
                    "thread_id": 101,
                }
            ],
            "Timer B": [
                {
                    "name": "Timer B",
                    "start_time": 45,
                    "stop_time": 55,
                    "thread_id": 101,
                }
            ],
            "Timer C": [
                {
                    "name": "Timer C",
                    "start_time": 40,
                    "stop_time": 50,
                    "thread_id": 100,
                }
            ],
        }
        self.assertCountEqual(formatted_timers, expected_formatted_timers)

        viewer_instance.show_thread_id = True
        formatted_timers = viewer_instance._format_timer_names(timers)
        expected_formatted_timers = {
            "Timer A\nthread: 100": [
                {
                    "name": "Timer A",
                    "start_time": 25,
                    "stop_time": 35,
                    "thread_id": 100,
                }
            ],
            "Timer A\nthread: 101": [
                {
                    "name": "Timer A",
                    "start_time": 33,
                    "stop_time": 43,
                    "thread_id": 101,
                }
            ],
            "Timer B\nthread: 101": [
                {
                    "name": "Timer B",
                    "start_time": 45,
                    "stop_time": 55,
                    "thread_id": 101,
                }
            ],
            "Timer C\nthread: 100": [
                {
                    "name": "Timer C",
                    "start_time": 40,
                    "stop_time": 50,
                    "thread_id": 100,
                }
            ],
        }
        self.assertCountEqual(formatted_timers, expected_formatted_timers)

    def test_sort_timers(self) -> None:
        """
        Tests sorting of timers by the `start_time` of the first block.
        When thread ID showing is enabled, then timers should be primarily sorted by their `thread_id`
        and then by `start_time`.
        """
        viewer_instance = Viewer()
        formatted_timers = {
            "Timer B": [
                {
                    "start_time": 45,
                    "thread_id": 100,
                }
            ],
            "Timer A": [
                {
                    "start_time": 25,
                    "thread_id": 101,
                }
            ],
            "Timer C": [
                {
                    "start_time": 40,
                    "thread_id": 101,
                }
            ],
            "Timer D": [
                {
                    "start_time": 33,
                    "thread_id": 100,
                }
            ],
        }

        sorted_timers = viewer_instance._sort_timers(formatted_timers)
        timer_names = list(sorted_timers.keys())
        self.assertEqual(timer_names[0], "Timer A")
        self.assertEqual(timer_names[1], "Timer D")
        self.assertEqual(timer_names[2], "Timer C")
        self.assertEqual(timer_names[3], "Timer B")

        viewer_instance.show_thread_id = True
        sorted_timers = viewer_instance._sort_timers(formatted_timers)
        timer_names = list(sorted_timers.keys())
        self.assertEqual(timer_names[0], "Timer D")
        self.assertEqual(timer_names[1], "Timer B")
        self.assertEqual(timer_names[2], "Timer A")
        self.assertEqual(timer_names[3], "Timer C")

    def test_coplete_timers_formatting(self) -> None:
        """
        Tests the complete pipeline from loading report files to generating formatted and sorted timers.
        """
        report_a = [
            {"name": "Timer A", "text": "Block A", "start_time": 25, "stop_time": 35, "thread_id": 100},
            {"name": "Timer B", "text": "Block B", "start_time": 45, "stop_time": 55, "thread_id": 101},
        ]
        report_b = [
            {"name": "Timer C", "text": "Block C", "start_time": 40, "stop_time": 50, "thread_id": 100},
            {"name": "Timer A", "text": "Block D", "start_time": 33, "stop_time": 43, "thread_id": 101},
        ]

        with tempfile.TemporaryDirectory() as temp_dir_name:
            with open(os.path.join(temp_dir_name, "waterfalls.json"), "w") as f:
                json.dump(report_a, f)
            with open(os.path.join(temp_dir_name, "waterfalls.1.json"), "w") as f:
                json.dump(report_b, f)

            viewer_instance = Viewer(directory=temp_dir_name)
            report_file_paths = viewer_instance._get_report_file_paths()
            blocks = viewer_instance._load_blocks_from_reports(report_file_paths)

        timers, time_total, time_min = viewer_instance._group_blocks_to_timers(blocks)
        timers = viewer_instance._format_timer_names(timers)
        timers = viewer_instance._sort_timers(timers)
        time_unit = viewer_instance._determine_time_unit(time_total)

        expected_timers = {
            "Timer A\nthread: 100": [
                {
                    "name": "Timer A",
                    "text": "Block A",
                    "start_time": 25,
                    "stop_time": 35,
                    "thread_id": 100,
                }
            ],
            "Timer A\nthread: 101": [
                {
                    "name": "Timer A",
                    "text": "Block D",
                    "start_time": 33,
                    "stop_time": 43,
                    "thread_id": 101,
                }
            ],
            "Timer B": [
                {
                    "name": "Timer B",
                    "text": "Block B",
                    "start_time": 45,
                    "stop_time": 55,
                    "thread_id": 101,
                }
            ],
            "Timer C": [
                {
                    "name": "Timer C",
                    "text": "Block C",
                    "start_time": 40,
                    "stop_time": 50,
                    "thread_id": 100,
                }
            ],
        }

        self.assertCountEqual(timers, expected_timers)
        self.assertEqual(time_unit.name, "nanoseconds")
        self.assertEqual(time_total, 30)
        self.assertEqual(time_min, 25)

    def test_determine_time_unit(self):
        """
        Tests automatic determination of time unit and a manual override.
        """
        viewer_instance = Viewer()
        time_unit = viewer_instance._determine_time_unit(time_total=-1)
        self.assertEqual(time_unit.name, "nanoseconds")

        time_unit = viewer_instance._determine_time_unit(time_total=0)
        self.assertEqual(time_unit.name, "nanoseconds")

        time_unit = viewer_instance._determine_time_unit(time_total=1)
        self.assertEqual(time_unit.name, "nanoseconds")

        time_unit = viewer_instance._determine_time_unit(time_total=1000)
        self.assertEqual(time_unit.name, "microseconds")

        time_unit = viewer_instance._determine_time_unit(time_total=999999)
        self.assertEqual(time_unit.name, "microseconds")

        time_unit = viewer_instance._determine_time_unit(time_total=1000000)
        self.assertEqual(time_unit.name, "milliseconds")

        time_unit = viewer_instance._determine_time_unit(time_total=1000000000)
        self.assertEqual(time_unit.name, "seconds")

        time_unit = viewer_instance._determine_time_unit(time_total=1000000000 * 60)
        self.assertEqual(time_unit.name, "minutes")

        time_unit = viewer_instance._determine_time_unit(time_total=1000000000 * 3600)
        self.assertEqual(time_unit.name, "hours")

        time_unit = viewer_instance._determine_time_unit(time_total=1000000000 * 3600 * 1234)
        self.assertEqual(time_unit.name, "hours")

        viewer_instance.user_time_unit = "msec"
        time_unit = viewer_instance._determine_time_unit(time_total=1000000000 * 3600 * 1234)
        self.assertEqual(time_unit.name, "milliseconds")

    def test_non_existent_directory(self) -> None:
        """
        Tests that trying to load report files from a non existent directory raises `SystemExit` exception.
        """
        viewer_instance = Viewer(directory="/nonexistent")
        with self.assertRaises(SystemExit):
            viewer_instance._get_report_file_paths()

    def test_empty_report_files(self) -> None:
        """
        Tests that when there is not even one timing block in any of the loaded report files,
        the `SystemExit` exception is raised.
        """
        with tempfile.TemporaryDirectory() as temp_dir_name:
            with open(os.path.join(temp_dir_name, "waterfalls.json"), "w") as file:
                json.dump([], file)
            with open(os.path.join(temp_dir_name, "waterfalls.1.json"), "w") as file:
                json.dump([], file)

            viewer_instance = Viewer(directory=temp_dir_name)
            report_file_paths = viewer_instance._get_report_file_paths()
            with self.assertRaises(SystemExit):
                viewer_instance._load_blocks_from_reports(report_file_paths)

    def test_save_as_image(self) -> None:
        """
        Tests that an image file is generated.
        """
        with tempfile.TemporaryDirectory() as temp_dir_name:
            report = [
                {
                    "name": "Timer A",
                    "text": None,
                    "start_time": 10,
                    "stop_time": 20,
                    "thread_duration": 5,
                    "thread_id": 100,
                }
            ]

            with open(os.path.join(temp_dir_name, "waterfalls.json"), "w") as file:
                json.dump(report, file)

            Viewer(directory=temp_dir_name, save_image=True).visualize_report()

            files = [f for f in os.listdir(temp_dir_name) if os.path.isfile(os.path.join(temp_dir_name, f))]

            self.assertIn("waterfalls.svg", files)

    def test_argument_parser(self):
        """
        Tests that command line arguments are parsed properly.
        """
        with patch("sys.argv", ["viewer.py"]):
            args = viewer._parse_arguments()
            self.assertEqual(args.directory, os.getcwd())
            self.assertIsNone(args.unit)
            self.assertFalse(args.thread_id)
            self.assertFalse(args.lines)
            self.assertFalse(args.image)

        with patch("sys.argv", ["viewer.py", "/path/to/records", "-u", "msec", "-tli"]):
            args = viewer._parse_arguments()
            self.assertEqual(args.directory, "/path/to/records")
            self.assertEqual(args.unit, "msec")
            self.assertTrue(args.thread_id)
            self.assertTrue(args.lines)
            self.assertTrue(args.image)


if __name__ == "__main__":
    unittest.main()
