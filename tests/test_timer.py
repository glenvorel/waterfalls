import concurrent.futures
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import List, Tuple
import unittest

from waterfalls import Timer


class TestTimer(unittest.TestCase):
    """
    Tests the `waterfalls.Timer` module.
    """

    def test_class_instances(self) -> None:
        """
        Tests timers defined as class instances where each `Timer` instance has multiple blocks.
        """
        timer_a, timer_b = self._create_class_blocks()

        # Assert number of instances
        self.assertEqual(len(Timer.instances), 2)

        # Assert timer names
        self.assertEqual(timer_a.name, "Timer A")
        self.assertEqual(timer_b.name, "Timer B")

        # Assert total number of blocks
        self.assertEqual(len(timer_a.blocks), 4)
        self.assertEqual(len(timer_b.blocks), 4)

        # Assert block texts
        self.assertIsNone(timer_a.blocks[0].text)
        self.assertEqual(timer_a.blocks[1].text, "Block A")
        self.assertEqual(timer_a.blocks[2].text, "Block B")
        self.assertIsNone(timer_a.blocks[3].text)
        self.assertEqual(timer_b.blocks[0].text, "Block C")
        self.assertEqual(timer_b.blocks[1].text, "Block D")
        self.assertEqual(timer_b.blocks[2].text, "Block E")
        self.assertIsNone(timer_b.blocks[3].text)

        # Assert thread durations
        for i in range(4):
            with self.subTest(i=i):
                self.assertGreaterEqual(timer_a.blocks[i].thread_duration, 0)
                self.assertGreaterEqual(timer_b.blocks[i].thread_duration, 0)

    def test_class_report(self) -> None:
        """
        Tests report generated from timers defined as class instances.
        """
        self._create_class_blocks()
        report = Timer.generate_report()
        self._assert_simple_report(report)

    def test_context_instances(self) -> None:
        """
        Tests timers defined as context managers where each `Timer` instance only has one block.
        """
        self._create_context_blocks()
        self._assert_1_to_1_instances()

    def test_context_report(self) -> None:
        """
        Tests report generated from timers defined as context managers.
        """
        self._create_context_blocks()
        report = Timer.generate_report()
        self._assert_simple_report(report)

    def test_decorator_instances(self) -> None:
        """
        Tests timers defined as function decorators where each `Timer` instance only has one block.
        """
        self._create_decorator_blocks()
        self._assert_1_to_1_instances()

    def test_decorator_report(self) -> None:
        """
        Tests report generated from timers defined as function decorators.
        """
        self._create_decorator_blocks()
        report = Timer.generate_report()
        self._assert_simple_report(report)

    def test_combined_report(self) -> None:
        """
        Tests report generated from timers defined as class instances, context managers
        and function decorators, one after another.
        """
        self._create_class_blocks()
        self._create_context_blocks()
        self._create_decorator_blocks()

        report = Timer.generate_report()

        # Assert total number of blocks
        self.assertEqual(len(report), 8 * 3)

        # Assert timer names
        self.assertEqual(len([b for b in report if b["name"] == "Timer A"]), 4 * 3)
        self.assertEqual(len([b for b in report if b["name"] == "Timer B"]), 4 * 3)

        # Assert block texts
        self.assertEqual(len([b for b in report if b["text"] == "Block A"]), 3)
        self.assertEqual(len([b for b in report if b["text"] == "Block B"]), 3)
        self.assertEqual(len([b for b in report if b["text"] == "Block C"]), 3)
        self.assertEqual(len([b for b in report if b["text"] == "Block D"]), 3)
        self.assertEqual(len([b for b in report if b["text"] == "Block E"]), 3)

        # Assert thread durations
        for i in range(8 * 3 - 1):
            with self.subTest(i=i):
                self.assertGreaterEqual(report[i]["thread_duration"], 0)

        # Assert thread IDs
        for i in range(8 * 3 - 1):
            with self.subTest(i=i):
                self.assertEqual(report[i]["thread_id"], report[i + 1]["thread_id"])

    def test_nested_report(self) -> None:
        """
        Tests that different types of timers can be created within one another.
        """

        @Timer("Decorator timer")
        def my_function(i):
            with Timer("Context timer"):
                timer = Timer("Class timer")
                timer.start(text=i)
                timer.stop()

        for i in range(2):
            my_function(i)

        report = Timer.generate_report()

        # Assert total number of blocks
        self.assertEqual(len(report), 6)

        # Assert timer names
        self.assertEqual(len([b for b in report if b["name"] == "Decorator timer"]), 2)
        self.assertEqual(len([b for b in report if b["name"] == "Context timer"]), 2)
        self.assertEqual(len([b for b in report if b["name"] == "Class timer"]), 2)

        # Assert block texts
        self.assertEqual(len([b for b in report if b["text"] == "0"]), 1)
        self.assertEqual(len([b for b in report if b["text"] == "1"]), 1)
        self.assertEqual(len([b for b in report if b["text"] is None]), 4)

        # Assert thread durations
        for i in range(6 - 1):
            with self.subTest(i=i):
                self.assertGreaterEqual(report[i]["thread_duration"], 0)

        # Assert thread IDs
        for i in range(6 - 1):
            with self.subTest(i=i):
                self.assertEqual(report[i]["thread_id"], report[i + 1]["thread_id"])

    def test_block_text(self) -> None:
        """
        Tests that `text` can be set in the constructor, in `start()` and in `stop()` methods.
        """
        timer_a = Timer("Tiemr A", "Block A")
        timer_a.start()
        timer_a.stop()

        timer_b = Timer("Timer B", "Block B")
        timer_b.start(text="Block B2")
        timer_b.stop()

        timer_c = Timer("Timer C", "Block C")
        timer_c.start()
        timer_c.stop(text="Block C3")

        timer_d = Timer("Timer D", "Block D")
        timer_d.start(text="Block D2")
        timer_d.stop(text="Block D3")

        timer_e = Timer("Timer E")
        timer_e.start()
        timer_e.stop(text="Block E3")

        report = Timer.generate_report()

        self.assertEqual(report[0]["text"], "Block A")
        self.assertEqual(report[1]["text"], "Block B2")
        self.assertEqual(report[2]["text"], "Block C3")
        self.assertEqual(report[3]["text"], "Block D3")
        self.assertEqual(report[4]["text"], "Block E3")

    def test_never_started(self) -> None:
        """
        Tests that a `Timer` can be created without being started - no report file should be saved.
        """
        timer = Timer("Timer A")
        report = Timer.generate_report()
        self.assertEqual(report, [])

        with self.assertLogs(level="WARNING"):
            report_files = self._save_report_files()
        self.assertEqual(len(report_files), 0)

    def test_prevent_double_start(self) -> None:
        """
        Tests two consecutive calls to `start()`.
        The second call should log a warning message.
        The timer must stay functioning and after another call to `stop()`
        it must generate a valid report.
        """
        timer = Timer("Timer A")
        timer.start()

        with self.assertLogs(level="WARNING"):
            timer.start()

        report = Timer.generate_report()
        self.assertEqual(len(report), 0)

        timer.stop()

        report = Timer.generate_report()
        self.assertEqual(len(report), 1)

    def test_prevent_stop_without_start(self) -> None:
        """
        Tests calling `stop()` without ever starting a timer.
        The call should log a warning message.
        The timer must stay functioning and after calls to `start()` and `stop()`
        it must generate a valid report.
        """
        timer = Timer("Timer A")

        with self.assertLogs(level="WARNING"):
            timer.stop()

        report = Timer.generate_report()
        self.assertEqual(len(report), 0)

        timer.start()
        timer.stop()

        report = Timer.generate_report()
        self.assertEqual(len(report), 1)

    def test_save_report(self) -> None:
        """
        Tests saving a report of a `Timer` created in the current thread.
        """
        with Timer("Timer A"):
            pass

        report_files = self._save_report_files()
        self.assertEqual(len(report_files), 1)

    def test_save_empty_report(self) -> None:
        """
        Tests an attempt to save a report without ever creating any `Timer` instance.
        """
        report_files = self._save_report_files()
        self.assertEqual(len(report_files), 0)

    def test_threaded_timing(self) -> None:
        """
        Tests two `Timer` instances, each created in its own thread.
        """

        def my_function(i):
            with Timer("Timer A", text=i):
                pass

        threads = []

        for i in range(2):
            t = threading.Thread(target=my_function, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        report = Timer.generate_report()
        self._assert_multithread_report(report)

        report_files = self._save_report_files()
        self.assertEqual(len(report_files), 1)

    def test_multiprocessing_timing(self) -> None:
        """
        Tests two `Timer` instances, each created in its own process.
        In this case, there should be two report files - each generated for its process.
        """
        with tempfile.TemporaryDirectory() as temp_dir_name:
            os.environ["WATERFALLS_DIRECTORY"] = temp_dir_name

            def my_function(i):
                with Timer("Timer A", text=i):
                    pass

            processes = []

            for i in range(2):
                p = multiprocessing.Process(target=my_function, args=(i,))
                processes.append(p)
                p.start()

            for p in processes:
                p.join()

            report_files = self._get_files_from_dir(temp_dir_name)

            self.assertEqual(len(report_files), 2)

            for report_file in report_files:
                with open(os.path.join(temp_dir_name, report_file)) as rf:
                    report = json.load(rf)
                    self.assertEqual(len(report), 1)

        del os.environ["WATERFALLS_DIRECTORY"]

    def test_concurrent_threading(self) -> None:
        """
        Tests two `Timer` instances, each created in its own thread within a thread pool.
        """

        def my_function(run):
            with Timer("Timer A", text=run):
                time.sleep(0.5)  # Put the worker to sleep so another thread is started

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            {executor.submit(my_function, run): run for run in range(2)}

        report = Timer.generate_report()

        self._assert_multithread_report(report)

        report_files = self._save_report_files()
        self.assertEqual(len(report_files), 1)

    def test_report_directory_path(self) -> None:
        """
        Tests that directory is properly determined based on priorities.
        """
        # The directory defaults to the current working directory
        directory = Timer._get_report_directory_path()
        self.assertEqual(directory, Path("."))

        # Directory defined as env variable has a higher priority
        os.environ["WATERFALLS_DIRECTORY"] = "./environ_directory"
        directory = Timer._get_report_directory_path()
        self.assertEqual(directory, Path("./environ_directory"))

        # Directory defined as class variable has a higher priority
        Timer.directory = "./cls_var_directory"
        directory = Timer._get_report_directory_path()
        self.assertEqual(directory, Path("./cls_var_directory"))

        # Directory defined as function argument has the highest priority
        directory = Timer._get_report_directory_path("./arg_directory")
        self.assertEqual(directory, Path("./arg_directory"))

    def test_report_file_name(self) -> None:
        """
        Tests that report file name is properly determined.
        When calling from a parent process, it should be plain, without PID.
        When called from a child process, it should contain PID.
        """
        file_name_is_main = Timer._get_report_file_name(is_main_process=True)
        self.assertEqual(file_name_is_main, "waterfalls.json")

        file_name_not_main = Timer._get_report_file_name(is_main_process=False)
        self.assertRegex(file_name_not_main, "waterfalls.[0-9]+.json")

        with tempfile.TemporaryDirectory() as temp_dir_name:
            os.environ["WATERFALLS_DIRECTORY"] = temp_dir_name

            def my_function():
                with Timer("Timer A"):
                    pass

            p = multiprocessing.Process(target=my_function)
            p.start()
            p.join()

            with Timer("Timer B"):
                pass
            Timer.save_report()

            report_files = self._get_files_from_dir(temp_dir_name)
            self.assertEqual(len(report_files), 2)
            self.assertIn("waterfalls.json", report_files)

            report_files.remove("waterfalls.json")
            self.assertRegex(report_files[0], "waterfalls.[0-9]+.json")

    def test_repr(self):
        """
        Tests the representation of `Timer`.
        """
        timer_a = Timer("Timer A")
        self.assertEqual(repr(timer_a), "Timer (name='Timer A', text=None)")

        timer_b = Timer("Timer B", "Block A")
        self.assertEqual(repr(timer_b), "Timer (name='Timer B', text='Block A')")

        timer_b.start("Block B")
        self.assertEqual(repr(timer_b), "Timer (name='Timer B', text='Block B')")

        timer_b.stop()
        self.assertEqual(repr(timer_b), "Timer (name='Timer B', text=None)")

        with Timer("Timer C") as timer_c:
            self.assertEqual(repr(timer_c), "Timer (name='Timer C', text=None)")

        with Timer("Timer D", text="Block D") as timer_d:
            self.assertEqual(repr(timer_d), "Timer (name='Timer D', text='Block D')")

    def tearDown(self) -> None:
        """
        Resets `Timer` instances after each test.
        """
        Timer.instances = []
        Timer.directory = None

    def _create_class_blocks(self) -> Tuple[Timer, Timer]:
        """
        Creates two `Timer` instances, each with multiple blocks.
        """
        timer_a = Timer("Timer A")
        timer_a.start()
        timer_a.stop()

        timer_a.start("Block A")
        timer_a.stop()

        timer_a.start("Block B")
        timer_a.stop()

        timer_a.start()
        timer_a.stop()

        timer_b = Timer("Timer B")
        timer_b.start("Block C")
        timer_b.stop()

        timer_b.start("Block D")
        timer_b.stop()

        timer_b.start("Block E")
        timer_b.stop()

        timer_b.start()
        timer_b.stop()

        return timer_a, timer_b

    @staticmethod
    def _create_context_blocks() -> None:
        """
        Creates multiple `Timer` instances, each defined as a context manager.
        """
        with Timer("Timer A"):
            pass

        with Timer("Timer A", text="Block A"):
            pass

        with Timer("Timer A", text="Block B"):
            pass

        with Timer("Timer A"):
            pass

        with Timer("Timer B", text="Block C"):
            pass

        with Timer("Timer B", text="Block D"):
            pass

        with Timer("Timer B", text="Block E"):
            pass

        with Timer("Timer B"):
            pass

    @staticmethod
    def _create_decorator_blocks() -> None:
        """
        Creates multiple `Timer` instances, each defined as a function decorator.
        """

        @Timer("Timer A")
        def my_function_a():
            pass

        @Timer("Timer A", text="Block A")
        def my_function_b():
            pass

        @Timer("Timer A", text="Block B")
        def my_function_c():
            pass

        @Timer("Timer A")
        def my_function_d():
            pass

        @Timer("Timer B", text="Block C")
        def my_function_e():
            pass

        @Timer("Timer B", text="Block D")
        def my_function_f():
            pass

        @Timer("Timer B", text="Block E")
        def my_function_g():
            pass

        @Timer("Timer B")
        def my_function_h():
            pass

        my_function_a()
        my_function_b()
        my_function_c()
        my_function_d()
        my_function_e()
        my_function_f()
        my_function_g()
        my_function_h()

    def _assert_simple_report(self, report: List[dict]) -> None:
        """
        Asserts a report generated by any of the timers defined as class instances,
        context managers and function decorators.

        Args:
            report: List of all timing blocks.
        """
        # Assert total number of blocks
        self.assertEqual(len(report), 8)

        # Assert timer names
        self.assertEqual(report[0]["name"], "Timer A")
        self.assertEqual(report[1]["name"], "Timer A")
        self.assertEqual(report[2]["name"], "Timer A")
        self.assertEqual(report[3]["name"], "Timer A")
        self.assertEqual(report[4]["name"], "Timer B")
        self.assertEqual(report[5]["name"], "Timer B")
        self.assertEqual(report[6]["name"], "Timer B")
        self.assertEqual(report[7]["name"], "Timer B")

        # Assert block texts
        self.assertIsNone(report[0]["text"])
        self.assertEqual(report[1]["text"], "Block A")
        self.assertEqual(report[2]["text"], "Block B")
        self.assertIsNone(report[3]["text"])
        self.assertEqual(report[4]["text"], "Block C")
        self.assertEqual(report[5]["text"], "Block D")
        self.assertEqual(report[6]["text"], "Block E")
        self.assertIsNone(report[7]["text"])

        # Assert start and stop times
        for i in range(7):
            with self.subTest(i=i):
                self.assertLessEqual(report[i]["start_time"], report[i]["stop_time"])

        # Assert thread durations
        for i in range(7):
            with self.subTest(i=i):
                self.assertGreaterEqual(report[i]["thread_duration"], 0)

        # Assert thread IDs
        for i in range(7):
            with self.subTest(i=i):
                self.assertEqual(report[i]["thread_id"], report[i + 1]["thread_id"])

    def _assert_multithread_report(self, report: List[dict]) -> None:
        """
        Asserts a report generated by two `Timer` instances, each in its own thread.

        Args:
            report: List of all timing blocks.
        """
        # Assert total number of blocks
        self.assertEqual(len(report), 2)

        # Assert timer names
        self.assertEqual(report[0]["name"], "Timer A")
        self.assertEqual(report[1]["name"], "Timer A")

        self.assertEqual(report[0]["text"], "0")
        self.assertEqual(report[1]["text"], "1")

        # Assert start and stop times
        self.assertLessEqual(report[0]["start_time"], report[0]["stop_time"])
        self.assertLessEqual(report[1]["start_time"], report[1]["stop_time"])

        # Assert thread durations
        self.assertGreaterEqual(report[0]["thread_duration"], 0)
        self.assertGreaterEqual(report[1]["thread_duration"], 0)

        # Assert thread IDs
        self.assertNotEqual(report[0]["thread_id"], report[1]["thread_id"])

        report_files = self._save_report_files()

        # Assert generated report files
        self.assertEqual(len(report_files), 1)
        self.assertEqual(report_files[0], "waterfalls.json")

    def _assert_1_to_1_instances(self) -> None:
        """
        Asserts timers which contain one block per one instance
        (e.g., created via context manager or function decorator).
        """
        # Assert number of instances
        self.assertEqual(len(Timer.instances), 8)

        # Assert timer names
        self.assertEqual(Timer.instances[0].name, "Timer A")
        self.assertEqual(Timer.instances[1].name, "Timer A")
        self.assertEqual(Timer.instances[2].name, "Timer A")
        self.assertEqual(Timer.instances[3].name, "Timer A")
        self.assertEqual(Timer.instances[4].name, "Timer B")
        self.assertEqual(Timer.instances[5].name, "Timer B")
        self.assertEqual(Timer.instances[6].name, "Timer B")
        self.assertEqual(Timer.instances[7].name, "Timer B")

        # Assert total number of blocks
        for i in range(7):
            with self.subTest(i=i):
                self.assertEqual(len(Timer.instances[i].blocks), 1)

        # Assert block texts
        self.assertIsNone(Timer.instances[0].blocks[0].text)
        self.assertEqual(Timer.instances[1].blocks[0].text, "Block A")
        self.assertEqual(Timer.instances[2].blocks[0].text, "Block B")
        self.assertIsNone(Timer.instances[3].blocks[0].text)
        self.assertEqual(Timer.instances[4].blocks[0].text, "Block C")
        self.assertEqual(Timer.instances[5].blocks[0].text, "Block D")
        self.assertEqual(Timer.instances[6].blocks[0].text, "Block E")
        self.assertIsNone(Timer.instances[7].blocks[0].text)

        # Assert thread durations
        for i in range(7):
            with self.subTest(i=i):
                self.assertGreaterEqual(Timer.instances[i].blocks[0].thread_duration, 0)

    def _save_report_files(self) -> List[str]:
        """
        Saves report(s) into report file(s).

        Returns:
            List of names of saved report files.
        """
        with tempfile.TemporaryDirectory() as temp_dir_name:
            Timer.save_report(directory=temp_dir_name)
            return self._get_files_from_dir(temp_dir_name)

    @staticmethod
    def _get_files_from_dir(directory: str) -> List[str]:
        """
        Lists all files in a directory, non-recursive.

        Args:
            directory: Where to look for files.

        Returns:
            List of all files in the specified `directory` or an empty list if the `directory` has no files.
        """
        return [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]


if __name__ == "__main__":
    unittest.main()
