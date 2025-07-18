#!/bin/env python

"""
tacho - Tachometer for your apps

"""

__version_info__ = ("0", "1", "0")
__version__ = ".".join(__version_info__)


import argparse
from dataclasses import dataclass
from enum import Enum, StrEnum, member, unique
import os
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any, TextIO, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    runs = parser.add_argument_group("number of runs")
    runs.add_argument(
        "-w",
        "--warmup",
        type=int,
        default=0,
        help="Before measuring run the command WARMUP times. This is useful to e.g. fill caches. (default=%(default)s)",
    )
    runs.add_argument(
        "-r",
        "--runs",
        type=int,
        help="Exact number of evaluations to perform. Without this option, tacho determines the number of runs automatically.",
    )
    runs.add_argument(
        "-m",
        "--min-runs",
        type=int,
        default=10,
        help="Minimum number of runs (default=%(default)s)",
    )
    runs.add_argument(
        "-M",
        "--max-runs",
        type=int,
        default=sys.maxsize,
        help="Maximum number of runs (default is unlimited)",
    )
    runs.add_argument(
        "-t",
        "--total-seconds",
        type=float,
        default=3.0,
        help="Total target time in seconds. (default=%(default)s)",
    )

    parser.add_argument(
        "-v", "--version", action="version", version="%(prog)s " + __version__
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Any command you can specify in a shell.",
    )

    measurements = parser.add_argument_group("events")
    measurements.add_argument(
        "-e",
        "--event",
        type=str,
        default="duration_time,context-switches,cpu-migrations,page-faults,cycles,branches,branch-misses,instructions",
        help='The performance monitoring unit (PMU) to select. This argument is directly passed to "perf stat". See "perf list" for a list of all events. (default=%(default)s)',
    )

    # parse args - show help & fail for no arguments
    if len(sys.argv) == 1:
        parser.error("no command provided")
    return parser.parse_args()


@dataclass
class Measurement:
    name: str
    values: list[float]
    unit: str = ""


def parse_perf_stat_csv(text: str, sep: str = ",") -> list[Measurement]:
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
        if len(line) < 3 or line[0] == "#":
            continue
        l = line.split(sep)

        if len(l) > 3 and len(l[0]) > 0 and len(l[2]) > 0:
            try:
                m = Measurement(name=l[2], values=[float(l[0])], unit=l[1])
                if m.name == "duration_time" and m.unit == "":
                    m.unit = "ns"

                # we want standard units, so recalculate nanoseconds
                if m.unit == "ns":
                    m.unit = "s"
                    m.values[0] /= 1e9
                elif m.unit == "msec":
                    m.unit = "s"
                    m.values[0] /= 1e3
                measurements.append(m)
            except ValueError:  #
                # can happen for e.g. "<not counted>" as l[0]
                pass

    return measurements


def run_perf(events: str, command: list[str], tmpfile: Any) -> list[Measurement]:
    """
    Runs 'perf stat' once and gathers measurement data, returns a list of measurements
    """
    # I use a huge interval time (1 year). That way we get only a single printout,
    # and that printout contains the total runtime.

    cmd = ["perf", "stat", "-o", tmpfile.name, "-x", ","]

    # perf startup is a lot slower when events are specified, so try to NOT specify it!
    if events != None:
        cmd += ["-e", events]
    cmd += command

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


@unique
class Tty(StrEnum):
    fg_bold_black = "\x1b[1;30m"
    fg_bold_red = "\x1b[1;31m"
    fg_bold_green = "\x1b[1;32m"
    fg_bold_yellow = "\x1b[1;33m"
    fg_bold_blue = "\x1b[1;34m"
    fg_bold_magenta = "\x1b[1;35m"
    fg_bold_cyan = "\x1b[1;36m"
    fg_bold_white = "\x1b[1;37m"

    fg_normal_black = "\x1b[0;30m"
    fg_normal_red = "\x1b[0;31m"
    fg_normal_green = "\x1b[0;32m"
    fg_normal_yellow = "\x1b[0;33m"
    fg_normal_blue = "\x1b[0;34m"
    fg_normal_magenta = "\x1b[0;35m"
    fg_normal_cyan = "\x1b[0;36m"
    fg_normal_white = "\x1b[0;37m"

    fg_black = "\x1b[30m"
    fg_red = "\x1b[31m"
    fg_green = "\x1b[32m"
    fg_yellow = "\x1b[33m"
    fg_blue = "\x1b[34m"
    fg_magenta = "\x1b[35m"
    fg_cyan = "\x1b[36m"
    fg_white = "\x1b[37m"

    bg_black = "\x1b[40m"
    bg_red = "\x1b[41m"
    bg_green = "\x1b[42m"
    bg_yellow = "\x1b[43m"
    bg_blue = "\x1b[44m"
    bg_magenta = "\x1b[45m"
    bg_cyan = "\x1b[46m"
    bg_white = "\x1b[47m"

    # see https://en.wikipedia.org/wiki/ANSI_escape_code#SGR_(Select_Graphic_Rendition)_parameters
    reset = "\x1b[0m"
    bold = "\x1b[1m"
    faint = "\x1b[2m"
    italic = "\x1b[3m"
    underline = "\x1b[4m"
    blink_slow = "\x1b[5m"
    blink_fast = "\x1b[6m"
    invert = "\x1b[7m"
    carriage_return = "\r"
    clear_to_eol = "\x1b[K"

    cursor_hide = "\033[?25l"
    cursor_show = "\033[?25h"


def metric_prefix(value: float, use_below_1: bool = True) -> Tuple[str, float]:
    metric = [
        ("T", 10**12),
        ("G", 10**9),
        ("M", 10**6),
        ("k", 10**3),
        ("", 10**0),
    ]
    if use_below_1:
        metric += [
            ("m", 10**-3),
            ("µ", 10**-6),
            ("n", 10**-9),
            ("p", 10**-12),
        ]

    for prefix, power in metric:
        v: float = value / power
        if v > 1 and v < 1000:
            return prefix, power

    return "", 1


def format_stat(values: list[Measurement], unit: str, name: str) -> str:
    # calculate factor
    mean: float = statistics.mean(values)
    if len(values) >= 2:
        stdev = statistics.stdev(values)
    else:
        stdev = 0.0

    # for count metrics (unit is "") we don't want to go show milis etc. E.g. milli context switches looks weird
    use_below_1 = len(unit) != 0
    prefix, power = metric_prefix(mean, use_below_1=use_below_1)

    relative_standard_deviation = 0.0
    if mean > 0:
        relative_standard_deviation = 100.0 * stdev / mean

    if relative_standard_deviation >= 15:
        deviation_color = Tty.fg_bold_red
    elif relative_standard_deviation >= 10:
        deviation_color = Tty.fg_red
    elif relative_standard_deviation >= 5:
        deviation_color = Tty.fg_yellow
    else:
        deviation_color = Tty.fg_green

    # print(
    #    f"{Tty.fg_bold_green}{mean/ power:10.2f}{Tty.reset} {Tty.fg_green}{prefix + unit:2}{Tty.reset}  ± {deviation_color}{relative_standard_deviation:5.1f} %{Tty.reset}  {Tty.bold}{name}{Tty.reset}"
    # )

    return f"{Tty.fg_bold_green}{mean/power:10.2f}{Tty.reset} {Tty.fg_green}{prefix+unit:2}{Tty.reset}  ± {deviation_color}{relative_standard_deviation:5.1f} %{Tty.reset}   {min(values)/power:6.2f} … {max(values)/power:6.2f}   {Tty.bold}{name}{Tty.reset}"


class BrailleGrayCodeSpinner:
    """
    A mesmerizing spinner based on braille gray code pattern.
    Also see https://github.com/manrajgrover/py-spinners/blob/master/spinners/spinners.py for plenty of other spinners
    """

    def __iter__(self) -> "BrailleGrayCodeSpinner":
        self._idx: int = 0
        return self

    def __next__(self) -> str:
        braille_start: int = 0x2800
        count = 0x100
        gray_code = self._idx ^ (self._idx >> 1)
        self._idx += 1
        if self._idx == count:
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
    if years > 0:
        out += f"{pre_num}{years}{post_num}Y "
    if len(out) != 0 or months > 0:
        out += f"{pre_num}{months}{post_num}M "
    if len(out) != 0 or days > 0:
        out += f"{pre_num}{days}{post_num}D "
    if len(out) != 0 or hours > 0:
        out += f"{pre_num}{hours}{post_num}:"

    out += f"{pre_num}{minutes:02}{post_num}:{pre_num}{seconds:02}{post_num}"
    return out


def term_width(fallback: int = 80) -> int:
    try:
        (width, _) = os.get_terminal_size()
    except OSError:
        width = fallback
    return width


class ProgressBar:
    def __init__(
        self,
        left_prefix: str = Tty.fg_bold_yellow,
        left_progress: str = "╸,━".split(","),
        left_fill: str = "━",
        right_prefix: str = Tty.fg_normal_blue,
        right_progress: str = "─,╶".split(","),
        right_fill: str = "─",
        finished_prefix: str = Tty.fg_bold_green,
        postfix: str = Tty.reset,
    ):
        self._left_prefix = left_prefix
        self._left_progress = left_progress
        self._left_fill = left_fill
        self._right_prefix = right_prefix
        self._right_progress = right_progress
        self._right_fill = right_fill
        self._finished_prefix = finished_prefix
        self._postfix = postfix

    def _calc_num_full_and_progress_idx(
        self, progress_01: float, width: int, num_progress: int
    ):
        ticks: int = int(round(progress_01 * (width * num_progress)))
        return divmod(ticks, num_progress)

    def render(self, progress_01: float, width: int = 80) -> str:
        if progress_01 <= 0:
            progress_01 = 0

        if progress_01 >= 1.0:
            return f"{self._finished_prefix}{self._left_fill * width}{self._postfix}"

        num_full, subticks_l = self._calc_num_full_and_progress_idx(
            progress_01=progress_01, width=width, num_progress=len(self._left_progress)
        )

        pb_left: str = self._left_fill * num_full
        if len(pb_left) < width:
            pb_left += self._left_progress[subticks_l]

        pb_right: str = ""
        if len(pb_left) < width:
            _, subticks_r = self._calc_num_full_and_progress_idx(
                progress_01=progress_01,
                width=width,
                num_progress=len(self._right_progress),
            )
            pb_right = self._right_progress[subticks_r]

        total_length = len(pb_left) + len(pb_right)
        if total_length < width:
            pb_right += self._right_fill * (width - total_length)

        return (
            f"{self._left_prefix}{pb_left}{self._right_prefix}{pb_right}{self._postfix}"
        )


class ProgressBars:
    standard = ProgressBar()

    no_color = ProgressBar(
        left_prefix="", right_prefix="", postfix="", finished_prefix=""
    )

    box = ProgressBar(
        left_progress=" ,▏,▎,▍,▌,▋,▊,▉".split(","),
        left_fill="█",
        right_progress=["·"],
        right_fill="·",
    )

    braille3 = ProgressBar(
        left_progress=" ,⠄,⠆,⠇,⠧,⠷,⠿".split(","),
        left_fill="⠿",
        right_progress="⠒,⠒,⠒,⠐,⠐,⠐".split(","),
        right_fill="⠒",
    )

    braille4 = ProgressBar(
        left_progress=" ,⡀,⡄,⡆,⡇,⣇,⣧,⣷,⣿".split(","),
        left_fill="⣿",
        right_progress="⠶,⠶,⠶,⠶,⠰,⠰,⠰,⠰".split(","),
        right_fill="⠶",
    )


def render(
    measures: list[Measurement],
    pb: ProgressBar,
    r: int,
    num_runs: int,
    width: int,
    num_lines_back: int,
) -> Tuple[str, int]:
    """
    Renders statistics, and returns the string and number of lines that were rendered.
    """
    out: str = ""
    if num_lines_back > 0:
        out += f"\x1b[{num_lines_back}F"

    text = f"Measuring {r+1}/{num_runs}"
    if r == 0:
        text = "Initial run"
    elif r >= num_runs:
        text = f"Done {r+1}/{r+1}"

    out += f"{Tty.carriage_return}|{pb.render((r+1)/(num_runs+1), width)}| {text}{Tty.clear_to_eol}\n"

    out += f"\n  {Tty.underline}    mean          %RSD      min      max   event type           {Tty.reset}{Tty.clear_to_eol}\n"
    for m in measures:
        out += f"{format_stat(m.values, m.unit, m.name)}{Tty.clear_to_eol}\n"

    return out, len(measures) + 3


def measure(args: argparse.Namespace) -> None:
    tmpfile = tempfile.NamedTemporaryFile(prefix="tacho_", mode="w+t")

    pb: ProgressBar = ProgressBars.standard

    total_runs = args.warmup
    width = 120

    for w in range(args.warmup):
        print(
            f"{Tty.carriage_return}|{pb.render(w/args.warmup, width)}| {w+1}/{args.warmup} warmup",
            end="",
        )
        run_perf(args.event, args.command, tmpfile)

    # first run to determine how long it takes
    time_before = time.time()
    print(f"{Tty.carriage_return}|{pb.render(0.0, width)}| Initial run...", end="")
    measures = run_perf(args.event, args.command, tmpfile)
    measured_runtime = time.time() - time_before

    num_runs: int = clamp(
        int(args.total_seconds / measured_runtime),
        args.min_runs - 1,  # we already did a run
        args.max_runs,
    )
    if args.runs:
        num_runs = args.runs - 1  # we already did a run

    # render everything, with stats:
    num_lines = 0
    for r in range(num_runs):
        out, num_lines = render(
            measures,
            pb=pb,
            r=r + 1,
            num_runs=num_runs,
            width=width,
            num_lines_back=num_lines,
        )
        sys.stdout.write(out)
        t_estimate = (time.time() - time_before) / (r + 1)
        t_remaining = t_estimate * (num_runs - r)
        integrate_measures(measures, run_perf(args.event, args.command, tmpfile))

    out, num_lines = render(
        measures,
        pb=pb,
        r=r + 1,
        num_runs=num_runs,
        width=width,
        num_lines_back=num_lines,
    )
    sys.stdout.write(out)


def main() -> None:
    args = parse_args()
    print(
        f"{Tty.cursor_hide}Benchmark: {Tty.bold}{' '.join(args.command)}{Tty.reset}\n"
    )
    measure(args)
    sys.stdout.write(Tty.cursor_show)


if __name__ == "__main__":
    main()
