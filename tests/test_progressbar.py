import time
import tacho


def test_progressbar():
    pb: tacho.ProgressBar = tacho.ProgressBars.no_color
    assert len(pb.render(998.0/1000, 30)) == 30

    max = 80*8
    all_pbs = set()
    print("")
    pb = tacho.ProgressBars.box
    print(tacho.Tty.cursor.hide, end="")
    for i in range(0, max+1):
        print(
            f"{tacho.Tty.util.carriage_return}|{pb.render(i/max, 80)}| {i}/{max}", end="")

        time.sleep(0.02)
        # assert not pb in all_pbs
        all_pbs.add(pb)
    time.sleep(1)
