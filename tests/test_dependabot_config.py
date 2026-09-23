""".github/dependabot.yml must only carry keys the v2 schema accepts.

Commit 4329d7b added an `automerge` block under the github-actions update.
GitHub-native Dependabot has no automerge option at all (it existed only on
the dependabot.com predecessor), and the v2 schema marks unknown keys as
additionalProperties: false -- the file failed config validation while
claiming a behavior that cannot happen. Real auto-merge is a repo setting
plus a workflow, not a dependabot.yml key.

The allowed key sets below mirror the published dependabot-2.0 schema
(json.schemastore.org/dependabot-2.0.json).
"""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEPENDABOT_YML = PROJECT_ROOT / ".github" / "dependabot.yml"

TOP_LEVEL_KEYS = {
    "version",
    "updates",
    "registries",
    "enable-beta-ecosystems",
    "multi-ecosystem-groups",
}

UPDATE_KEYS = {
    "allow", "assignees", "commit-message", "cooldown", "directories",
    "directory", "exclude-paths", "groups", "ignore",
    "insecure-external-code-execution", "labels", "milestone",
    "multi-ecosystem-group", "name", "open-pull-requests-limit",
    "package-ecosystem", "patterns", "pull-request-branch-name",
    "rebase-strategy", "registries", "schedule", "target-branch",
    "vendor", "versioning-strategy",
}


def _config():
    return yaml.safe_load(DEPENDABOT_YML.read_text(encoding="utf-8"))


def test_dependabot_config_exists_and_has_required_shape():
    config = _config()
    assert isinstance(config, dict), "dependabot.yml must be a mapping"
    assert config["version"] == 2
    assert isinstance(config["updates"], list) and config["updates"]


def test_dependabot_top_level_keys_are_schema_valid():
    config = _config()
    unknown = sorted(set(config) - TOP_LEVEL_KEYS)
    assert not unknown, (
        f"dependabot.yml top-level keys not in the v2 schema: {unknown}"
    )


def test_dependabot_update_keys_are_schema_valid():
    config = _config()
    violations = []
    for index, update in enumerate(config["updates"]):
        assert isinstance(update, dict), f"updates[{index}] must be a mapping"
        unknown = sorted(set(update) - UPDATE_KEYS)
        if unknown:
            ecosystem = update.get("package-ecosystem", "?")
            violations.append(f"updates[{index}] ({ecosystem}): {unknown}")
    assert not violations, (
        "dependabot.yml update entries carry keys the v2 schema rejects "
        "(additionalProperties: false); the file fails validation:\n  "
        + "\n  ".join(violations)
    )


def test_every_update_names_ecosystem_directory_and_schedule():
    config = _config()
    for index, update in enumerate(config["updates"]):
        assert "package-ecosystem" in update, f"updates[{index}]"
        assert {"directory", "directories"} & set(update), f"updates[{index}]"
        assert "schedule" in update, f"updates[{index}]"
