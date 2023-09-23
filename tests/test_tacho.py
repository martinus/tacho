import tacho


def test_spinner():
    spinner = tacho.BrailleGrayCodeSpinner()
    it = iter(spinner)
    assert next(it) == chr(0x2800)
    assert next(it) != chr(0x2800)

    for n in range(1000):
        n = next(it)
        assert n >= chr(0x2800)
        assert n < chr(0x2900)
