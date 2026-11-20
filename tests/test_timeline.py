import pytest

from halcyon.timeline import keyframes, mirror, sample


def test_mirror_reflects_dusk_onto_dawn():
    m = mirror({0.0: 1.0, 0.25: 2.0, 0.5: 3.0})
    assert m == {0.0: 1.0, 0.25: 2.0, 0.5: 3.0, 0.75: 2.0}


def test_mirror_rejects_morning_keys():
    with pytest.raises(ValueError):
        mirror({0.6: 1.0})


def test_keyframes_sorted_and_closed_at_one():
    kf = keyframes({0.5: 3.0, 0.0: 1.5})
    assert list(kf) == ["0.000000", "0.500000", "1.000000"]
    assert kf["1.000000"] == kf["0.000000"] == 1.5


def test_keyframes_reject_out_of_range():
    with pytest.raises(ValueError):
        keyframes({1.2: 0.0})


def test_sample_interpolates_numbers_and_colors_with_wraparound():
    assert sample({0.0: 0.0, 0.5: 10.0}, 0.25) == 5.0
    assert sample({0.0: 0.0, 0.5: 10.0}, 0.75) == 5.0  # wraps back to the 0.0 value at 1.0
    assert sample({0.0: [0, 0, 0], 1.0: [10, 20, 30]}, 0.5) == [5, 10, 15]
