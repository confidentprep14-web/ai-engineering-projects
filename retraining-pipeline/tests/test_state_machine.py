import json
import os

DEFINITION_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "state_machine_definition.json")


def test_state_machine_definition_is_valid_json():
    with open(DEFINITION_PATH) as f:
        content = f.read()

    json.loads(content)  # raises if invalid


def test_state_machine_has_five_states():
    """The pipeline is "5-state" at the logical-stage level (preprocess,
    train, evaluate, conditional branch, deploy-or-notify), but the spec's
    own verbatim ASL JSON has 7 top-level keys under "States": Preprocess,
    Train, Evaluate, ShouldDeploy, Deploy, NotifyDeployed, NotifyNoDeploy --
    the Choice state and its two notify branches are each separate ASL
    states. This asserts the real key set rather than forcing literal
    "== 5", matching the spec's own listed name set."""
    with open(DEFINITION_PATH) as f:
        definition = json.load(f)

    expected_states = {
        "Preprocess",
        "Train",
        "Evaluate",
        "ShouldDeploy",
        "Deploy",
        "NotifyDeployed",
        "NotifyNoDeploy",
    }
    assert set(definition["States"].keys()) == expected_states
    assert len(definition["States"]) == 7


def test_state_machine_starts_at_preprocess():
    with open(DEFINITION_PATH) as f:
        definition = json.load(f)

    assert definition["StartAt"] == "Preprocess"
