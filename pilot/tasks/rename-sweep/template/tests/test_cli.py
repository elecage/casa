from jobq.cli import cli_overrides


def test_cli_deadline_flag_maps_to_setting_key():
    assert cli_overrides(["--deadline-ms", "250"]) == {"deadline_ms": 250}
