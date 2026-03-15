from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from tix.config import Config, ConfigError, create_default_config, load_config


VALID_TOML = """\
[zendesk]
subdomain = "mycompany"
email = "alice@example.com"

[git]
repo_path = "/tmp/repo"

[app]
sync_interval_seconds = 600
terminal = "iTerm"
claude_launch_command = "claude --resume"

[board]
columns = ["Triage", "WIP", "Done"]
warn_after_hours = 12
"""

MINIMAL_TOML = """\
[zendesk]
subdomain = "acme"
email = "bob@acme.com"

[git]
repo_path = "/tmp/repo"
"""


class TestLoadValidConfig:
    def test_load_valid_config(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(VALID_TOML)
        os.chmod(cfg_file, 0o600)
        monkeypatch.setenv("ZENDESK_API_TOKEN", "tok123")

        cfg = load_config(cfg_file)

        assert cfg.zendesk_subdomain == "mycompany"
        assert cfg.zendesk_email == "alice@example.com"
        assert cfg.zendesk_token == "tok123"
        assert cfg.repo_path == Path("/tmp/repo").resolve()
        assert cfg.sync_interval_seconds == 600
        assert cfg.terminal == "iTerm"
        assert cfg.claude_launch_command == "claude --resume"
        assert cfg.column_names == ["Triage", "WIP", "Done"]
        assert cfg.warn_after_hours == 12


class TestLoadMissingFile:
    def test_load_missing_file_raises(self, tmp_path):
        missing = tmp_path / "nope.toml"
        with pytest.raises(ConfigError, match="Config file not found"):
            load_config(missing)


class TestLoadMissingToken:
    def test_load_missing_token_raises(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(MINIMAL_TOML)
        os.chmod(cfg_file, 0o600)
        monkeypatch.delenv("ZENDESK_API_TOKEN", raising=False)

        with pytest.raises(ConfigError, match="ZENDESK_API_TOKEN"):
            load_config(cfg_file)


class TestLoadInvalidSubdomain:
    @pytest.mark.parametrize("bad", ["", "-leading", "has space", "under_score!"])
    def test_load_invalid_subdomain_raises(self, bad, tmp_path, monkeypatch):
        toml_text = f"""\
[zendesk]
subdomain = "{bad}"
email = "x@x.com"

[git]
repo_path = "/tmp/repo"
"""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(toml_text)
        os.chmod(cfg_file, 0o600)
        monkeypatch.setenv("ZENDESK_API_TOKEN", "tok")

        with pytest.raises(ConfigError, match="Invalid zendesk.subdomain"):
            load_config(cfg_file)


class TestLoadDefaults:
    def test_load_defaults(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(MINIMAL_TOML)
        os.chmod(cfg_file, 0o600)
        monkeypatch.setenv("ZENDESK_API_TOKEN", "tok")

        cfg = load_config(cfg_file)

        assert cfg.sync_interval_seconds == 300
        assert cfg.base_branch == "main"
        assert cfg.terminal is None
        assert cfg.claude_launch_command == "cld -r"
        assert cfg.column_names == ["Triage", "Investigating", "Waiting", "In Review", "Done"]
        assert cfg.warn_after_hours == 24
        assert len(cfg.staleness_rules) == 3


class TestCreateDefaultConfig:
    def test_creates_file(self, tmp_path):
        dest = tmp_path / "example.toml"
        result = create_default_config(dest)

        assert result == dest
        assert dest.exists()

    def test_file_contains_expected_sections(self, tmp_path):
        dest = tmp_path / "example.toml"
        create_default_config(dest)
        content = dest.read_text()

        assert "[zendesk]" in content
        assert "[git]" in content
        assert "[app]" in content
        assert "[board]" in content

    def test_does_not_overwrite_existing(self, tmp_path):
        dest = tmp_path / "example.toml"
        dest.write_text("original")
        create_default_config(dest)

        assert dest.read_text() == "original"


class TestCreateDefaultConfigPermissions:
    def test_file_has_0600_permissions(self, tmp_path):
        dest = tmp_path / "example.toml"
        create_default_config(dest)

        mode = dest.stat().st_mode & 0o777
        assert mode == 0o600


class TestPathExpansion:
    def test_tilde_expanded_in_repo_path(self, tmp_path, monkeypatch):
        toml_text = """\
[zendesk]
subdomain = "acme"
email = "a@b.com"

[git]
repo_path = "~/my-repo"
worktree_dir = "~/worktrees"
"""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(toml_text)
        os.chmod(cfg_file, 0o600)
        monkeypatch.setenv("ZENDESK_API_TOKEN", "tok")

        cfg = load_config(cfg_file)

        assert "~" not in str(cfg.repo_path)
        assert cfg.repo_path.is_absolute()
        assert "~" not in str(cfg.worktree_dir)
        assert cfg.worktree_dir.is_absolute()
