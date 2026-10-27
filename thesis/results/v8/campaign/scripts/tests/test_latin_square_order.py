"""Order turn (item 2, thesis/results/v8/DECISIONS.md): regression tests
for build_latin_square_profile_orders() (replaces run_window()'s old
independent-per-window rng.shuffle(), which confounded profile identity
with window/position -- Decision 89, pilot 2's own single real window)
and for run_instance_warmup() (the new fixed-time, once-per-installation,
pre-first-block warmup -- see its own docstring in campaign_run.py).
"""
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import campaign_run as cr


def test_latin_square_is_a_real_latin_square_across_many_seeds():
    """For 200 different seeds: each window's profile_order must be a
    permutation of PROFILES (row constraint, trivially true by
    construction), AND each position (0/1/2) must see each profile
    exactly once across the 3 windows (column constraint -- the actual
    new guarantee this replaces the old independent shuffle with)."""
    for seed in range(200):
        orders = cr.build_latin_square_profile_orders(seed)
        assert set(orders.keys()) == {1, 2, 3}
        for window, order in orders.items():
            assert sorted(order) == sorted(cr.PROFILES), f"seed={seed} window={window}: not a permutation"
        for position in range(3):
            column = {orders[w][position] for w in (1, 2, 3)}
            assert column == set(cr.PROFILES), (
                f"seed={seed} position={position}: column = {column}, not all 3 profiles -- "
                f"not a Latin square"
            )


def test_latin_square_is_deterministic_per_seed():
    """Same seed -> identical square every time (needed so window{NN}.json's
    own recorded seed is enough to reproduce/verify the square later,
    without needing to also store every window's order separately)."""
    for seed in (0, 1, 42, 123456):
        a = cr.build_latin_square_profile_orders(seed)
        b = cr.build_latin_square_profile_orders(seed)
        assert a == b


def test_latin_square_covers_multiple_distinct_squares_across_seeds():
    """Not degenerate to a single hardcoded order regardless of seed --
    different seeds must be able to produce different window-1 orders."""
    window1_orders = {tuple(cr.build_latin_square_profile_orders(seed)[1]) for seed in range(30)}
    assert len(window1_orders) > 1, "every seed produced the same window-1 order -- not actually randomized"


def test_latin_square_rejects_mismatched_profile_and_window_counts():
    with mock.patch.object(cr, "WINDOWS_PER_CAMPAIGN", 4):
        try:
            cr.build_latin_square_profile_orders(seed=1)
            assert False, "expected ValueError for len(PROFILES) != WINDOWS_PER_CAMPAIGN"
        except ValueError:
            pass


def test_instance_warmup_runs_for_the_configured_duration_then_tears_down():
    """run_instance_warmup(): must (1) pick a scenario via the same
    inventory-scoping rule as run_window(), (2) bring proxies up, (3) call
    run_warmup() repeatedly until the (tiny, test-scaled) duration elapses,
    writing into _campaign-control/instance_warmup/ -- never a real
    scenario_dir() path, (4) tear proxies down even though nothing failed."""
    calls = []

    def fake_start_block_proxies(executor, installation, profile, scenarios, window):
        calls.append(("start_block_proxies", installation, profile, tuple(scenarios), window))

    def fake_stop_block_proxies(executor, installation, profile, scenarios, window):
        calls.append(("stop_block_proxies", installation, profile, tuple(scenarios), window))

    def fake_run_warmup(executor, installation, scenario, profile, window, scenario_path):
        calls.append(("run_warmup", installation, profile, scenario, window, str(scenario_path)))

    executor = mock.Mock(spec=cr.SSHExecutor)
    executor.inventory = {"clients": {"L0@sa-east-1": {}, "L325@sa-east-1": {}}}

    with tempfile.TemporaryDirectory() as tmp, \
         mock.patch.object(cr, "DATA_ROOT", Path(tmp)), \
         mock.patch.object(cr, "start_block_proxies", fake_start_block_proxies), \
         mock.patch.object(cr, "stop_block_proxies", fake_stop_block_proxies), \
         mock.patch.object(cr, "run_warmup", fake_run_warmup):
        cr.run_instance_warmup(executor, "sa-east-1", duration_seconds=0.3)

    kinds = [c[0] for c in calls]
    assert kinds[0] == "start_block_proxies"
    assert kinds[-1] == "stop_block_proxies"
    warmup_calls = [c for c in calls if c[0] == "run_warmup"]
    assert len(warmup_calls) >= 1, "expected at least one disposable warmup flow in 0.3s"
    for c in warmup_calls:
        assert "instance_warmup" in c[-1], f"warmup wrote outside instance_warmup/: {c}"
        assert "sa-east-1" in c[-1]


def test_instance_warmup_skips_installation_with_no_available_scenario():
    """Same 'skip, don't abort the campaign' philosophy as the
    installation-skip fix (item 3): an installation entirely absent from
    this run's own inventory must be skipped cleanly, no exception."""
    calls = []
    executor = mock.Mock(spec=cr.SSHExecutor)
    executor.inventory = {"clients": {"L0@sa-east-1": {}}}  # nothing for ap-northeast-1

    with mock.patch.object(cr, "start_block_proxies", lambda *a, **k: calls.append("start")), \
         mock.patch.object(cr, "stop_block_proxies", lambda *a, **k: calls.append("stop")), \
         mock.patch.object(cr, "run_warmup", lambda *a, **k: calls.append("warmup")):
        cr.run_instance_warmup(executor, "ap-northeast-1", duration_seconds=5)

    assert calls == [], f"expected no calls for an installation with no scenario in inventory, got {calls}"


if __name__ == "__main__":
    test_latin_square_is_a_real_latin_square_across_many_seeds()
    test_latin_square_is_deterministic_per_seed()
    test_latin_square_covers_multiple_distinct_squares_across_seeds()
    test_latin_square_rejects_mismatched_profile_and_window_counts()
    test_instance_warmup_runs_for_the_configured_duration_then_tears_down()
    test_instance_warmup_skips_installation_with_no_available_scenario()
    print("PASS: all latin square / instance warmup tests")
