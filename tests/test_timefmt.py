from pd.timefmt import format_seconds


def test_format_seconds_matches_design_example():
    assert format_seconds(13 * 60 + 13.986) == "13:13.986"


def test_format_seconds_pads_zero():
    assert format_seconds(3.5) == "00:03.500"
