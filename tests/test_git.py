# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""
import pytest
import subprocess

from synth_wiki.git import is_available, is_repo, init, add, commit, auto_commit, status, last_commit


class TestGit:
    def test_is_available(self):
        assert is_available() is True

    def test_init_creates_repo(self, tmp_path):
        init(str(tmp_path))
        assert is_repo(str(tmp_path))

    def test_is_repo_false_for_non_repo(self, tmp_path):
        assert is_repo(str(tmp_path)) is False

    def test_add_and_commit(self, tmp_path):
        init(str(tmp_path))
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], capture_output=True)

        (tmp_path / "test.txt").write_text("hello")
        add(str(tmp_path), "test.txt")
        commit(str(tmp_path), "initial commit")

        h, msg = last_commit(str(tmp_path))
        assert h != ""
        assert msg == "initial commit"

    def test_status_shows_changes(self, tmp_path):
        init(str(tmp_path))
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], capture_output=True)

        (tmp_path / "file.txt").write_text("content")
        s = status(str(tmp_path))
        assert "file.txt" in s

    def test_auto_commit(self, tmp_path):
        init(str(tmp_path))
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], capture_output=True)

        (tmp_path / "auto.txt").write_text("auto content")
        auto_commit(str(tmp_path), "auto commit")

        h, msg = last_commit(str(tmp_path))
        assert h != ""
        assert msg == "auto commit"

    def test_commit_nothing_to_commit(self, tmp_path):
        init(str(tmp_path))
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"], capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], capture_output=True)

        commit(str(tmp_path), "empty")

    def test_last_commit_no_commits(self, tmp_path):
        init(str(tmp_path))
        h, msg = last_commit(str(tmp_path))
        assert h == ""
        assert msg == ""
