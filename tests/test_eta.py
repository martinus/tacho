import tacho


def test_eta():
    # [0s, 1h(
    assert tacho.eta(3.7) == "00:04"
    assert tacho.eta(0) == "00:00"
    assert tacho.eta(0.499) == "00:00"
    assert tacho.eta(0.500001) == "00:01"
    assert tacho.eta(60 * 60 - 1) == "59:59"

    # [1h, 24h(
    assert tacho.eta(60 * 60) == "1:00:00"
    assert tacho.eta(3600 * 7 + 60 * 43 + 12) == "7:43:12"
    assert tacho.eta(86400 - 1) == "23:59:59"

    # [1d, 2629746s(
    assert tacho.eta(86400) == "1D 0:00:00"
    assert tacho.eta(2629746 - 1) == "30D 10:29:05"

    # [2629746s, ...(
    assert tacho.eta(2629746) == "1M 0D 0:00:00"
    assert tacho.eta(1e9) == "31Y 8M 8D 1:28:40"


def test_eta_pre_post():
    # [0s, 1h(
    assert tacho.eta(3.7, pre_num="a", post_num="b") == "a00b:a04b"
    assert tacho.eta(0) == "00:00"
    assert tacho.eta(0.499) == "00:00"
    assert tacho.eta(0.500001) == "00:01"
    assert tacho.eta(60 * 60 - 1) == "59:59"

    # [1h, 24h(
    assert tacho.eta(60 * 60) == "1:00:00"
    assert tacho.eta(3600 * 7 + 60 * 43 + 12) == "7:43:12"
    assert tacho.eta(86400 - 1) == "23:59:59"

    # [1d, 2629746s(
    assert tacho.eta(86400) == "1D 0:00:00"
    assert tacho.eta(2629746 - 1) == "30D 10:29:05"

    # [2629746s, ...(
    assert tacho.eta(2629746) == "1M 0D 0:00:00"
    assert tacho.eta(1e9, pre_num="a", post_num="b") == "a31bY a8bM a8bD a1b:a28b:a40b"
