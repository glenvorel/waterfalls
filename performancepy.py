#!/usr/bin/python3
"""
Records performance of running python scripts to find bottlenecks.

Using of this module consists of two steps.

Step 1
======
It is imported and instantiated in all scripts that are to be measured.
When the scripts are executed, PerformancePy automatically generates
performance records in CSV format.

Example:
    import time
    from performancepy import PerformancePy

    pp = PerformancePy('producer', '/path/to/records')

    for i in range(10):
        pp.start('working hard')
        time.sleep(0.2)
        pp.dump()
        time.sleep(0.1)

Step 2
======
The records generated in the first step are loaded
and PerformancePy produces a visual chart in HTML format.
The chart file is saved in the records directory.

Example:
    $ python performancepy.py --directory "/path/to/records"

More info on https://www.github.com/glenvorel/performancepy
"""
import datetime
import os
import threading


class PerformancePy:
    """
    Args:
        group (str): Name of a group of tasks, typically represents one threat or process.
        directory (str, optional): Directory where record files will be created.
            If not specified, the directory where is performancepy.py located will be used.
        bias (int, optional): Time zone bias in minutes (e.g., UTC+8 is 480 minutes).
    """
    def __init__(self, group, directory='.', bias=0):
        self.group = group

        self.filepath = self._get_filepath(directory)
        with open(self.filepath, 'w') as df_file:
            df_file.write('Task,Start,Finish,Description,Color\n')

        self.bias = bias * 60

        # Properties related to each task
        self._start_time = None
        self._task = None
        self._color = None

    def _get_filepath(self, directory):
        directory_fullpath = os.path.realpath(directory)
        if not os.path.exists(directory_fullpath):
            os.makedirs(directory_fullpath)
        filename = '{}-{}.csv'.format(self.group, os.getpid())
        return os.path.join(directory_fullpath, filename)

    def start(self, task, color='na'):
        """
        Starts a task.

        Args:
            task (str): Name of a the task.
            color (str, optional): Color code of the task in hex format (e.g., '#000000').
                If not specified, PerformancePy will automatically assign it a color
                when generating the chart.
        """
        if self._start_time is not None:
            raise RuntimeError('PerformancePy is already running. Use .dump() to stop it first.')

        self._start_time = datetime.datetime.now(
            tz=datetime.timezone(datetime.timedelta(seconds=self.bias)))
        self._task = task
        self._color = color

    def dump(self):
        """
        Ends a task and dumps its duration to the record file.
        """
        if self._start_time is None:
            raise RuntimeError('PerformancePy is not running. Use .start() to start it first.')

        end_time = datetime.datetime.now(
            tz=datetime.timezone(datetime.timedelta(seconds=self.bias)))
        duration = end_time - self._start_time
        duration = round(duration.total_seconds() * 1000)
        task_name = '[{}-p{}t{}] {}'.format(
            self.group,
            os.getpid(),
            threading.current_thread().getName(),
            self._task)
        row = '{},{},{},{} ms,{}\n'.format(
            task_name,
            self._start_time.strftime('%Y-%m-%d %H:%M:%S.%f'),
            end_time.strftime('%Y-%m-%d %H:%M:%S.%f'),
            duration,
            self._color
            )
        with open(self.filepath, 'a') as df_file:
            df_file.write(row)
        self._start_time = None


if __name__ == '__main__':
    import argparse
    import hashlib
    import re

    import pandas as pd
    import plotly
    import plotly.figure_factory as ff

    def _render_chart():
        parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument(
            '--directory',
            default='.',
            help='Directory containing generated CSV files.\
            Used also to store the generated HTML chart file.\
            Example: --directory "/path/to/records".\
            Default: this module\'s directory.')
        parser.add_argument(
            '--bias',
            default='0',
            help='Time zone bias in minutes (e.g., UTC+8 is 480 minutes).\
            Used for time stamp in the generated file.\
            Example: --bias 480.\
            Default: 0.')
        parser.add_argument(
            '--durationonly',
            default=False,
            action='store_true',
            help='On hover gantt bars, show only task duration in milliseconds.\
            Default: Show task duration in milliseconds, start/end time stamp and the task name.')
        args = parser.parse_args()

        directory = os.path.realpath(args.directory)

        dataframes = []

        for file in sorted(os.listdir(directory)):
            if not file.endswith('.csv'):
                continue
            dataframe = pd.read_csv(os.path.join(directory, file))
            dataframes.append(dataframe)

        if not dataframes:
            raise FileNotFoundError(
                ('No CSV file found in directory "{}".\n'.format(directory) +
                 'Specify directory using the "--directory" argument.\n'
                 'See "performancepy.py --help" for usage details.'))

        merged_df = pd.concat(dataframes)

        def make_color_map():
            color_list = ['#008080', '#70a494', '#b4c8a8', '#f6edbd',
                          '#edbb8a', '#de8a5a', '#ca562c']
            all_tasks = merged_df.Task.unique()
            task_types = list({re.search('] .+', task).group()[2:] for task in all_tasks})
            color_map = {}
            for task in all_tasks:
                for task_type in task_types:
                    if task_type in task:
                        # Find color for this task type
                        # based on the first appearance in the dataframe
                        df_color = (merged_df[merged_df['Task'].str.contains(task_type)]
                                    .head(1).Color.values[0])
                        # If color has been specified, use it
                        if df_color != 'na':
                            color_map[task] = df_color
                        # Else, use color from built-in list of colors
                        else:
                            hash_sha = hashlib.sha224(str.encode(task_type)).hexdigest()
                            hasn_num = 0
                            for char in hash_sha:
                                hasn_num += ord(char)
                            index = hasn_num % len(color_list)
                            color = color_list[index]
                            color_map[task] = color
            return color_map

        color_map = make_color_map()

        fig = ff.create_gantt(merged_df, colors=color_map, index_col='Task',
                              title='PerformancePy', show_colorbar=False, bar_width=0.4,
                              showgrid_x=True, showgrid_y=True, group_tasks=True)

        # Show only duration value
        if args.durationonly:
            for fig_data in fig['data']:
                fig_data.update(hovertemplate='%{text}')

        # Hide range buttons
        fig.update_layout(xaxis={'rangeselector': {'visible': False}})

        bias = int(args.bias) * 60
        timestamp = datetime.datetime.now(
            tz=datetime.timezone(datetime.timedelta(seconds=bias))).strftime('%y%m%d%H%M%S')
        filepath = os.path.join(directory, 'performancepy_{}.html'.format(timestamp))

        plotly.offline.plot(fig, filename=filepath)

    _render_chart()
