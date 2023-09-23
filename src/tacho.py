#!/bin/env python

"""
tacho - Tachometer for your apps

"""

__version_info__ = ('0', '1', '0')
__version__ = '.'.join(__version_info__)


import argparse
from dataclasses import dataclass
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
    print(type(tmpfile))

    for w in range(args.warmup):
        run_perf(args.event, args.command, tmpfile)

    # first run to determine how long it takes
    time_before = time.time()
    measures = run_perf(args.event, args.command, tmpfile)
    measured_runtime = time.time() - time_before

    num_runs: int = clamp(int(args.total_seconds / measured_runtime),
                          args.min_runs - 1,  # we already did a run
                          args.max_runs)
    if (args.runs):
        num_runs = args.runs

    BOLD = '\033[1m'
    ENDC = '\033[0m'
    CYAN = '\033[96m'

    for r in range(num_runs):
        t_estimate = (time.time() - time_before) / (r+1)
        t_remaining = t_estimate * (num_runs - r)
        print(f"{r+1:4}/{num_runs} ETA {eta(t_remaining)}, num_runs-r={num_runs - r})")
        integrate_measures(measures,
                           run_perf(args.event, args.command, tmpfile))

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
    Fancy format of duration into an ETA string:
    00:09 # just seconds
    02:03 # seconds + minutes
    07:02:09 # 7 hours, 2 minutes 9 seconds
    1 D 17:02  # 1 day, 17 hours, 2 minutes
    """
    t: int = round(seconds)

    # see https://en.cppreference.com/w/cpp/chrono/duration

    out: str = ""

    # years
    if (t >= 31556952):
        out += f"{pre_num}{t // 31556952}{post_num}Y "
        t %= 31556952

    # months
    if (len(out) != 0 or t >= 2629746):
        out += f"{pre_num}{t // 2629746}{post_num}M "
        t %= 2629746

    # days
    if (len(out) != 0 or t >= 86400):
        out += f"{pre_num}{t // 86400}{post_num}D "
        t %= 86400

    # hours
    if (len(out) != 0 or t >= 3600):
        out += f"{pre_num}{t // 3600:02}{post_num}:"
        t %= 3600

    # minutes
    out += f"{pre_num}{t // 60:02}{post_num}:"
    t %= 60

    # seconds
    out += f"{pre_num}{t:02}{post_num}"
    return out


class Cli:
    CLEAR_LINE = "\033[K"
    CURSOR_BACK = "\r"
    CURSOR_HIDE = "\033[?25l"
    CURSOR_SHOW = "\033[?25h"

    def __init__(self, stream: TextIO = sys.stdout) -> None:
        self._stream = stream

    def clear(self) -> None:
        self._stream.write(Cli.CURSOR_BACK)
        self._stream.write(Cli.CLEAR_LINE)

    def _render_frame(self) -> None:
        self.clear()

    def spin(self) -> None:
        spinner = BrailleGrayCodeSpinner()
        it = iter(spinner)

        self._stream.write(Cli.CURSOR_HIDE)
        for _ in range(10000):
            self.clear()
            self._stream.write(next(it))
            self._stream.write(" hello?")
            time.sleep(0.0125)


def main() -> None:
    args = parse_args()

    print(args)
    print(f"Benchmark: {' '.join(args.command)}")
    # cli = Cli()
    # cli.spin()
    measure(args)


if __name__ == '__main__':
    time
    main()
