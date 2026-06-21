import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import read_violations  # noqa: E402
from enable_capture import build_data_capture_config  # noqa: E402

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample_violation_report.json")


def _load_fixture() -> dict:
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def test_parse_violation_returns_plain_english():
    report = _load_fixture()
    result = read_violations.parse_monitoring_report(report)

    assert len(result) == 2
    assert "age" in result[0]
    assert "0.0008" in result[0]


def test_parse_violation_mentions_expected_threshold():
    report = _load_fixture()
    result = read_violations.parse_monitoring_report(report)

    assert "0.05" in result[0]


def test_enable_capture_config_has_correct_s3_path():
    config = build_data_capture_config("s3://my-ml-training-bucket/p3-10/capture/", capture_percentage=100)

    assert config["DestinationS3Uri"].startswith("s3://")
    assert config["InitialSamplingPercentage"] == 100


def test_baseline_json_structure():
    report = _load_fixture()

    assert "violations" in report
    for violation in report["violations"]:
        assert "feature_name" in violation
        assert "metric" in violation
