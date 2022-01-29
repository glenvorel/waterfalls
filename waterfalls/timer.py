"""
Measures the execution time of code blocks and CPU usage while executing the blocks.

When the user's code finishes, this module automatically generates reports
and saves them into the specified directory.
The reports can then be loaded by waterfalls.Viewer which shows them as a graph.

The waterfalls.Timer can be used as a class:

    t = Timer("Some task")
    t.start()
    # Do something
    t.stop()

As a context manager:

    with Timer("Some task"):
        # Do something

As a decorator:

    @Timer("Some task")
    def my_function():
        # Do something
"""

from __future__ import annotations

from atexit import register
from collections import namedtuple
from contextlib import ContextDecorator
from json import dump
from logging import getLogger
from multiprocessing import current_process
from os import environ, getcwd, getpid
from pathlib import Path
from threading import get_native_id
from time import perf_counter_ns, thread_time_ns
from typing import List, Optional


logger = getLogger(__name__)


Block = namedtuple("Block", ["start_time", "stop_time", "thread_duration", "text"])


class Timer(ContextDecorator):
    """
    Class for timing blocks of code and generating reports.

    When the user program exits, `Timer` automatically generates reports and save them into the specified directory.
    The reports can then be loaded by the waterfalls.Viewer to show them as a graph.
    """

    instances: List[Timer] = []
    directory: Optional[str] = None

    def __init__(self, name: str, text: Optional[str] = None) -> None:
        """
        Constructs an instance of waterfalls.Timer.

        Args:
            name: Name of the timer.
            text: Text of the first timing block, useful when using `Timer` as decorator or context manager.
        """
        self.name: str = name
        self.text: Optional[str] = str(text) if text is not None else None
        self.blocks: List[Block] = []
        self.thread_id: int = get_native_id()
        self._start_time: Optional[int] = None
        self._start_thread_time: int = 0
        self._is_main_process: bool = current_process().name == "MainProcess"

        self.__class__.instances.append(self)

    def start(self, text: Optional[str] = None) -> None:
        """
        Starts a timing block.

        Args:
            text: Text of the timing block.
        """
        if self._start_time is not None:
            logger.warning("Timer can't be started twice. Use .stop() to stop it first.")
            return

        if text is not None:
            self.text = str(text)

        self._start_time = perf_counter_ns()
        self._start_thread_time = thread_time_ns()

    def stop(self, text: Optional[str] = None) -> None:
        """
        Stops a timing block.

        Args:
            text: Text of the timing block.
        """
        if self._start_time is None:
            logger.warning("Timer hasn't been started yet. Use .start() to start it first.")
            return

        if text is not None:
            self.text = str(text)

        self.blocks.append(
            Block(
                start_time=self._start_time,
                stop_time=perf_counter_ns(),
                thread_duration=thread_time_ns() - self._start_thread_time,
                text=self.text,
            )
        )
        self._start_time = None
        self.text = None

        if not self._is_main_process:
            # Python doesn't honor `atexit` registrations in forked processes (https://bugs.python.org/issue39675).
            # When running in a child process, generate the report immediately
            self.save_report(is_main_process=False)

    @classmethod
    def generate_report(cls) -> List[dict]:
        """
        Generates report of the current process.

        Returns:
            List of dictionaries, each dictionary representing one timing block.
        """
        report = []

        for instance in cls.instances:
            for block in instance.blocks:
                report.append(
                    dict(
                        name=instance.name,
                        text=block.text,
                        start_time=block.start_time,
                        stop_time=block.stop_time,
                        thread_duration=block.thread_duration,
                        thread_id=instance.thread_id,
                    )
                )

        return report

    @classmethod
    def save_report(cls, directory: Optional[str] = None, is_main_process: bool = True) -> None:
        """
        Saves report of the current process.

        Args:
            directory: When set, the report will be saved into this directory.
            is_main_process: Should be `True` if function is called from main process,
                `False` if called from a child process.
        """
        if not cls.instances:
            # This method runs even when `waterfalls` is only imported and no `Timer` instance is created
            return

        report = cls.generate_report()
        if not report:
            logger.warning("No Timer block has been created, report will not be saved.")
            return

        report_directory_path = cls._get_report_directory_path(directory)
        report_file_name = cls._get_report_file_name(is_main_process)
        report_directory_path.mkdir(parents=True, exist_ok=True)
        report_file_path = report_directory_path.joinpath(report_file_name)

        with open(report_file_path, "w") as report_file:
            dump(report, report_file)

        logger.info("Waterfalls report saved into file '%s'", report_file_path.resolve())

    @classmethod
    def _get_report_directory_path(cls, directory: Optional[str] = None) -> Path:
        """
        Determines the directory for saving the report.

        Returns:
            A `Path` object of the directory into which the report will be saved.
        """
        if directory is not None:
            return Path(directory)
        if cls.directory is not None:
            return Path(cls.directory)
        if environ.get("WATERFALLS_DIRECTORY") is not None:
            return Path(environ["WATERFALLS_DIRECTORY"])
        return Path(getcwd())

    @staticmethod
    def _get_report_file_name(is_main_process: bool) -> str:
        """
        Determines the report file name.
        When `Timer` is running in a forked (child) process, the file name contains the process ID
        to avoid overwriting report files in programs using multiple processes.

        Args:
            is_main_process: Should be `True` if function is called from main process,
                `False` if called from a child process.

        Returns:
            File name of the report.
        """
        if is_main_process:
            return "waterfalls.json"
        return f"waterfalls.{getpid()}.json"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} (name={self.name!r}, text={self.text!r})"

    def __enter__(self) -> Timer:
        self.start()
        return self

    def __exit__(self, *exception_info) -> None:
        self.stop()


register(Timer.save_report)
