#!/bin/env python

"""
tacho - Tachometer for your apps

"""

__version_info__ = ('0', '1', '0')
__version__ = '.'.join(__version_info__)


import argparse
from dataclasses import dataclass
from enum import Enum, StrEnum, member, unique
import os
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any, TextIO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    runs = parser.add_argument_group("number of runs")
    runs.add_argument('-w', '--warmup', type=int, default=0,
                      help="Before measuring run the command WARMUP times. This is useful to e.g. fill caches. (default=%(default)s)")
    runs.add_argument('-r', '--runs', type=int,
                      help='Exact number of evaluations to perform. Without this option, tacho determines the number of runs automatically.')
    runs.add_argument('-m', '--min-runs', type=int, default=10,
                      help="Minimum number of runs (default=%(default)s)")
    runs.add_argument('-M', '--max-runs', type=int, default=sys.maxsize,
                      help='Maximum number of runs (default is unlimited)')
    runs.add_argument('-t', '--total-seconds', type=float, default=3.0,
                      help="Total target time in seconds. (default=%(default)s)")

    parser.add_argument('-v', '--version', action='version',
                        version='%(prog)s ' + __version__)
    parser.add_argument('command', nargs=argparse.REMAINDER,
                        help='Any command you can specify in a shell.')

    measurements = parser.add_argument_group("events")
    measurements.add_argument('-e', '--event', type=str, default='duration_time,context-switches,cpu-migrations,page-faults,cycles,branches,instructions',
                              help='The performance monitoring unit (PMU) to select. This argument is directly passed to "perf stat". See "perf list" for a list of all events. (default=%(default)s)')

    # parse args - show help & fail for no arguments
    if len(sys.argv) == 1:
        parser.error("no command provided")
    return parser.parse_args()


@dataclass
class Measurement:
    name: str
    values: list[float]
    unit: str = "count"


def parse_perf_stat_csv(text: str, sep: str = ',') -> list[Measurement]:
    """
    Parses 'perf stat -x' output.
    According to "man perf stat", the fileds are:
    0: counter value
    1: unit of the counter value or empty
    2: event name
    4: run time of counter
    """
    measurements = []
    for line in text.splitlines():
        if (len(line) < 3 or line[0] == '#'):
            continue
        l = line.split(sep)

        m = Measurement(
            name=l[2],
            values=[float(l[0])],
            unit="count" if len(l[1]) == 0 else l[1])

        # we want standard units, so recalculate nanoseconds
        if m.unit == "ns":
            m.unit = "s"
            m.values[0] /= 1e9
        measurements.append(m)
    return measurements


def run_perf(events: str, command: list[str], tmpfile: Any) -> list[Measurement]:
    """
    Runs 'perf stat' once and gathers measurement data, returns a list of measurements
    """
    # I use a huge interval time (1 year). That way we get only a single printout,
    # and that printout contains the total runtime.
    cmd = ["perf", "stat", "-o", tmpfile.name,
           "-x", ",", "-e", events] + command

    # run program, hiding all output so it doesn't interfere with our progress bar output
    tmpfile.truncate(0)
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    tmpfile.seek(0)
    return parse_perf_stat_csv(tmpfile.read())


def integrate_measures(totals: list[Measurement], new_run: list[Measurement]) -> None:
    for t, n in zip(totals, new_run):
        t.values += n.values


def clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(value, hi))


def measure(args: argparse.Namespace) -> None:
    tmpfile = tempfile.NamedTemporaryFile(prefix="tacho_", mode="w+t")

    pb: ProgressBar = ProgressBars.box
    print(Tty.cursor.hide, end="")

    total_runs = args.warmup
    width = 120

    for w in range(args.warmup):
        print(f"{Tty.util.carriage_return}|{pb.render(w/args.warmup, width)}| {w+1}/{args.warmup} warmup", end="")
        run_perf(args.event, args.command, tmpfile)
    if (args.warmup > 0):
        print(
            f"{Tty.util.carriage_return}|{pb.render(1.0, width)}| {args.warmup}/{args.warmup} warmup")

    # first run to determine how long it takes
    time_before = time.time()
    print(f"{Tty.util.carriage_return}|{pb.render(0.0, width)}| Initial run...", end="")

    measures = run_perf(args.event, args.command, tmpfile)

    measured_runtime = time.time() - time_before

    num_runs: int = clamp(int(args.total_seconds / measured_runtime),
                          args.min_runs - 1,  # we already did a run
                          args.max_runs)
    if (args.runs):
        num_runs = args.runs

    for r in range(num_runs):
        print(f"{Tty.util.carriage_return}{Tty.util.clear_to_eol}|{pb.render((r+1)/(num_runs+1), width)}| Measuring", end="")
        t_estimate = (time.time() - time_before) / (r+1)
        t_remaining = t_estimate * (num_runs - r)
        integrate_measures(measures,
                           run_perf(args.event, args.command, tmpfile))

    print(f"{Tty.util.carriage_return}|{pb.render(1.0, width)}| {r+2}/{num_runs+1} Measuring done!")
    for m in measures:
        print(
            f"{statistics.mean(m.values)} +- {statistics.stdev(m.values)} {m.unit} {m.name}")


class BrailleGrayCodeSpinner:
    """
    A mesmerizing spinner based on braille gray code pattern.
    Also see https://github.com/manrajgrover/py-spinners/blob/master/spinners/spinners.py for plenty of other spinners
    """

    def __iter__(self) -> 'BrailleGrayCodeSpinner':
        self._idx: int = 0
        return self

    def __next__(self) -> str:
        braille_start: int = 0x2800
        count = 0x100
        gray_code = self._idx ^ (self._idx >> 1)
        self._idx += 1
        if (self._idx == count):
            self._idx = 0
        return chr(braille_start + gray_code)


def eta(seconds: float, pre_num: str = "", post_num: str = "") -> str:
    """
    Fancy format of duration into an ETA string
    """

    # constants taken from https://en.cppreference.com/w/cpp/chrono/duration
    t: int = round(seconds)
    years, t = divmod(t, 31556952)
    months, t = divmod(t, 2629746)
    days, t = divmod(t, 86400)
    hours, t = divmod(t, 3600)
    minutes, seconds = divmod(t, 60)

    out: str = ""
    if (years > 0):
        out += f"{pre_num}{years}{post_num}Y "
    if (len(out) != 0 or months > 0):
        out += f"{pre_num}{months}{post_num}M "
    if (len(out) != 0 or days > 0):
        out += f"{pre_num}{days}{post_num}D "
    if (len(out) != 0 or hours > 0):
        out += f"{pre_num}{hours}{post_num}:"

    out += f"{pre_num}{minutes:02}{post_num}:{pre_num}{seconds:02}{post_num}"
    return out


class Tty:
    def my_code(a: int, b: int) -> str:
        return f"\x1B[{a};{b}m"

    def fg(num: int) -> str:
        return Tty.my_code(0, 30+num)

    def bg(num: int) -> str:
        return Tty.my_code(0, 40+num)

    def fg_bright(num: int) -> str:
        return Tty.my_code(0, 90+num)

    def bg_bright(num: int) -> str:
        return Tty.my_code(1, 40+num)


class Tty:
    @unique
    class fg(StrEnum):
        black = Tty.fg(0)
        red = Tty.fg(1)
        green = Tty.fg(2)
        yellow = Tty.fg(3)
        blue = Tty.fg(4)
        magenta = Tty.fg(5)
        cyan = Tty.fg(6)
        white = Tty.fg(7)

    @unique
    class bg(StrEnum):
        black = Tty.bg(0)
        red = Tty.bg(1)
        green = Tty.bg(2)
        yellow = Tty.bg(3)
        blue = Tty.bg(4)
        magenta = Tty.bg(5)
        cyan = Tty.bg(6)
        white = Tty.bg(7)

    @unique
    class util(StrEnum):
        reset = "\x1B[0m"
        bold = "\x1B[1m"
        carriage_return = "\r"
        clear_to_eol = "\x1B[K"

    @unique
    class cursor(StrEnum):
        hide = "\033[?25l"
        show = "\033[?25h"


def term_width(fallback: int = 80) -> int:
    try:
        (width, _) = os.get_terminal_size()
    except OSError:
        width = fallback
    return width


class ProgressBar:
    def __init__(self,
                 left_prefix: str = Tty.fg.yellow,
                 left_progress: str = "╸,━".split(','),
                 left_fill: str = "━",
                 right_prefix: str = Tty.fg.blue,
                 right_progress: str = "─,╶".split(','),
                 right_fill: str = "─",
                 finished_prefix: str = Tty.fg.green,
                 postfix: str = Tty.util.reset):
        self._left_prefix = left_prefix
        self._left_progress = left_progress
        self._left_fill = left_fill
        self._right_prefix = right_prefix
        self._right_progress = right_progress
        self._right_fill = right_fill
        self._finished_prefix = finished_prefix
        self._postfix = postfix

    def _calc_num_full_and_progress_idx(self, progress_01: float, width: int, num_progress: int):
        ticks: int = int(round(progress_01 * (width*num_progress)))
        return divmod(ticks, num_progress)

    def render(self, progress_01: float, width: int = 80) -> str:
        if (progress_01 <= 0):
            progress_01 = 0

        if (progress_01 >= 1.0):
            return f"{self._finished_prefix}{self._left_fill * width}{self._postfix}"

        num_full, subticks_l = self._calc_num_full_and_progress_idx(
            progress_01=progress_01, width=width, num_progress=len(self._left_progress))

        pb_left: str = self._left_fill * num_full
        if (len(pb_left) < width):
            pb_left += self._left_progress[subticks_l]

        pb_right: str = ""
        if len(pb_left) < width:
            _, subticks_r = self._calc_num_full_and_progress_idx(
                progress_01=progress_01, width=width, num_progress=len(self._right_progress))
            pb_right = self._right_progress[subticks_r]

        total_length = len(pb_left) + len(pb_right)
        if total_length < width:
            pb_right += self._right_fill * (width - total_length)

        return f"{self._left_prefix}{pb_left}{self._right_prefix}{pb_right}{self._postfix}"


class ProgressBars:
    standard = ProgressBar()

    no_color = ProgressBar(
        left_prefix="",
        right_prefix="",
        postfix="",
        finished_prefix="")

    box = ProgressBar(
        left_progress=" ,▏,▎,▍,▌,▋,▊,▉".split(','),
        left_fill="█",
        right_progress=["·"],
        right_fill="·")

    braille3 = ProgressBar(
        left_progress=" ,⠄,⠆,⠇,⠧,⠷,⠿".split(','),
        left_fill="⠿",
        right_progress="⠒,⠒,⠒,⠐,⠐,⠐".split(','),
        right_fill="⠒")

    braille4 = ProgressBar(
        left_progress=" ,⡀,⡄,⡆,⡇,⣇,⣧,⣷,⣿".split(','),
        left_fill="⣿",
        right_progress="⠶,⠶,⠶,⠶,⠰,⠰,⠰,⠰".split(','),
        right_fill="⠶")


#
#    def __init__(self, stream: TextIO = sys.stdout) -> None:
#        self._stream = stream
#
#    def clear(self) -> None:
#        self._stream.write(tty.util.carriage_return)
#        self._stream.write(Cli.CLEAR_LINE)
#
#    def _render_frame(self) -> None:
#        self.clear()
#
#    def spin(self) -> None:
#        spinner = BrailleGrayCodeSpinner()
#        it = iter(spinner)
#
#        self._stream.write(Cli.CURSOR_HIDE)
#        for _ in range(10000):
#            self.clear()
#            self._stream.write(next(it))
#            self._stream.write(" hello?")
#            time.sleep(0.0125)
#

def main() -> None:
    args = parse_args()
    print(f"Benchmark: {' '.join(args.command)}")

    measure(args)


if __name__ == '__main__':
    main()
