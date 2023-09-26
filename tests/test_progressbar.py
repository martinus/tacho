import time
import tacho


def test_progressbar():
    pb: tacho.ProgressBar = tacho.ProgressBars.no_color
    assert len(pb.render(998.0/1000, 30)) == 30

    max = 80*8
    all_pbs = set()
    print("")
    pb = tacho.ProgressBars.box
    print(tacho.Tty.cursor_hide, end="")
    for i in range(0, max+1):
        print(f"{tacho.Tty.carriage_return}|{pb.render(i/max, 80)}| {i}/{max}", end="")

        time.sleep(0.02)
        # assert not pb in all_pbs
        all_pbs.add(pb)
    time.sleep(1)


def test_color_output():
    tty = tacho.Tty
    print(
        f"\n  Time ({tty.bold + tty.fg_green}mean{tty.reset} ± {tty.fg_green}σ{tty.reset}):     61.001 s ±  0.000 s")
