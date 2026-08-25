"""The personal-use configuration and library manager.

`personal_config.py` is the one module a user reaches directly rather than
through an import: `quick_install.sh` and `quick_install.ps1` both point new
users at `python personal_config.py setup`. It has had no tests, which is how
three defects survived in the two functions a first-time user hits first.

* `PersonalConfig.load` did `cls(**data)` straight from the JSON. A config
  written by a different version of Chameleon -- or hand-edited, which is the
  entire point of a personal config file -- produced a bare
  `TypeError: __init__() got an unexpected keyword argument`, and the tool
  would not start.
* A malformed file raised `json.JSONDecodeError` with a traceback and no
  indication of which file was at fault.
* `create_playlist` stamped every playlist with `Path.home().stat().st_mtime`
  -- the *home directory's* modification time, identical for every playlist
  and unrelated to when any of them was made.

Every test here passes an explicit path. None of them may touch the real
`~/.chameleon`.
"""

import json
from pathlib import Path

import pytest

import personal_config


@pytest.fixture
def config_path(tmp_path):
    return tmp_path / "personal_config.json"


# --- defaults -------------------------------------------------------------

def test_defaults_are_populated_by_post_init():
    config = personal_config.PersonalConfig()

    # Declared as None on the dataclass and filled in by __post_init__; a
    # regression here gives every caller a None where a list is expected.
    assert config.supported_formats == ['.wav', '.wave']
    assert config.favorite_operations == ['normalize', 'analyze', 'denoise']


def test_defaults_match_the_charters_wav_only_scope():
    # CHARTER.md §3: the dependency-free product is honestly WAV-only.
    assert set(personal_config.PersonalConfig().supported_formats) == {'.wav', '.wave'}


# --- round trip -----------------------------------------------------------

def test_saving_then_loading_returns_the_same_settings(config_path):
    original = personal_config.PersonalConfig(
        audio_library="/tmp/library", performance_mode="fast", auto_backup=False)
    original.save(config_path)

    assert personal_config.PersonalConfig.load(config_path) == original


def test_loading_a_missing_file_writes_the_defaults(config_path):
    assert not config_path.exists()

    config = personal_config.PersonalConfig.load(config_path)

    assert config_path.exists()
    assert config == personal_config.PersonalConfig()
    assert json.loads(config_path.read_text())["performance_mode"] == "balanced"


def test_save_creates_the_parent_directory(tmp_path):
    nested = tmp_path / "a" / "b" / "config.json"

    personal_config.PersonalConfig().save(nested)

    assert nested.exists()


# --- tolerating other versions' files ------------------------------------

def test_an_unrecognised_setting_is_ignored_not_fatal(config_path, caplog):
    config_path.write_text(json.dumps(
        {"audio_library": "/tmp/keep-me", "setting_from_the_future": True}))

    config = personal_config.PersonalConfig.load(config_path)

    assert config.audio_library == "/tmp/keep-me"      # the known key survives
    assert "setting_from_the_future" in caplog.text     # and the user is told


def test_a_partial_config_falls_back_to_defaults_per_field(config_path):
    config_path.write_text(json.dumps({"performance_mode": "safe"}))

    config = personal_config.PersonalConfig.load(config_path)

    assert config.performance_mode == "safe"
    assert config.supported_formats == ['.wav', '.wave']


def test_malformed_json_names_the_file_and_says_what_to_do(config_path):
    config_path.write_text("{ not json at all")

    with pytest.raises(ValueError) as excinfo:
        personal_config.PersonalConfig.load(config_path)

    message = str(excinfo.value)
    assert str(config_path) in message
    assert "delete" in message.lower()


def test_a_json_document_that_is_not_an_object_is_rejected(config_path):
    config_path.write_text("[1, 2, 3]")

    with pytest.raises(ValueError, match="JSON object"):
        personal_config.PersonalConfig.load(config_path)


def test_loading_a_bad_file_does_not_overwrite_it(config_path):
    # Silently replacing a user's settings with defaults would lose them.
    config_path.write_text("{ not json at all")

    with pytest.raises(ValueError):
        personal_config.PersonalConfig.load(config_path)

    assert config_path.read_text() == "{ not json at all"


# --- library manager ------------------------------------------------------

@pytest.fixture
def manager(tmp_path):
    config = personal_config.PersonalConfig(audio_library=str(tmp_path / "library"))
    (tmp_path / "library").mkdir()
    instance = personal_config.PersonalLibraryManager.__new__(
        personal_config.PersonalLibraryManager)
    instance.config = config
    instance.library_path = Path(config.audio_library)
    instance.db_path = tmp_path / "library.json"
    instance.library_db = {"files": {}, "playlists": {}, "tags": {}}
    return instance


def test_playlists_created_at_different_times_get_different_timestamps(manager):
    manager.create_playlist("first", ["a.wav"])
    created_first = manager.library_db["playlists"]["first"]["created"]

    manager.create_playlist("second", ["b.wav"])
    created_second = manager.library_db["playlists"]["second"]["created"]

    # The old implementation returned the home directory's mtime for both.
    from datetime import datetime
    datetime.fromisoformat(created_first)      # parses as a real timestamp
    assert created_first <= created_second


def test_a_playlist_keeps_its_files(manager):
    manager.create_playlist("mix", ["a.wav", "b.wav"])

    assert manager.library_db["playlists"]["mix"]["files"] == ["a.wav", "b.wav"]
    assert json.loads(manager.db_path.read_text())["playlists"]["mix"]["files"] == [
        "a.wav", "b.wav"]


def test_tags_are_added_to_matching_files_only(manager):
    manager.library_db["files"] = {
        "drums/kick.wav": {"tags": []},
        "drums/snare.wav": {"tags": ["existing"]},
        "vocals/lead.wav": {"tags": []},
    }

    manager.add_tags("drums/*", ["percussion"])

    assert manager.library_db["files"]["drums/kick.wav"]["tags"] == ["percussion"]
    assert set(manager.library_db["files"]["drums/snare.wav"]["tags"]) == {
        "existing", "percussion"}
    assert manager.library_db["files"]["vocals/lead.wav"]["tags"] == []


def test_tagging_is_idempotent(manager):
    manager.library_db["files"] = {"a.wav": {"tags": []}}

    manager.add_tags("*", ["loud"])
    manager.add_tags("*", ["loud"])

    assert manager.library_db["files"]["a.wav"]["tags"] == ["loud"]


def test_search_matches_filenames_and_tags(manager):
    manager.library_db["files"] = {
        "drums/kick.wav": {"tags": ["percussion"]},
        "vocals/lead.wav": {"tags": ["dry"]},
    }

    assert manager.search("kick") == ["drums/kick.wav"]
    assert manager.search("percussion") == ["drums/kick.wav"]
    assert manager.search("VOCALS") == ["vocals/lead.wav"]     # case-insensitive
    assert manager.search("nothing here") == []


def test_search_does_not_return_duplicates_when_name_and_tag_both_match(manager):
    manager.library_db["files"] = {"kick.wav": {"tags": ["kick"]}}

    assert manager.search("kick") == ["kick.wav"]


# --- the workflows that admit they are unimplemented ----------------------

@pytest.mark.parametrize("workflow", ["podcast_workflow", "music_workflow"])
def test_placeholder_workflows_raise_and_point_at_the_real_commands(workflow, tmp_path):
    # These used to print step banners and a success line while doing nothing.
    with pytest.raises(NotImplementedError) as excinfo:
        getattr(personal_config.PersonalWorkflow, workflow)(
            tmp_path / "in.wav", tmp_path / "out")

    assert "chameleon" in str(excinfo.value)
