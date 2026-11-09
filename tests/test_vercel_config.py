import json
from pathlib import Path


def test_only_main_deploys_on_vercel():
    # "*" does not match branch names with a slash (feature/x); "**" does.
    config = json.loads((Path(__file__).parent.parent / "vercel.json").read_text())
    assert config["git"]["deploymentEnabled"] == {"main": True, "**": False}
