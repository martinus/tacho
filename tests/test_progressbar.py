import tacho


def test_progressbar():
    pb: str = tacho.progress_bar(998.0/1000, 30)
    assert len(pb) == 30

    max = 80*8
    # app progressbars should be different
    all_pbs = set()
    print("")
    for i in range(0, max+1):
        pb: str = tacho.progress_bar(i/max, 80)
        assert len(pb) == 80
        print(f"[{pb}] {i}/{max}")
        assert not pb in all_pbs
        all_pbs.add(pb)
