"""Tests for the destructive-bash detector.

The hook went from regex-on-raw-string matching to shlex-tokenized
per-segment matching to fix two classes of bug:
  - False positives from quoted substrings (`grep "git push" file`).
  - False negatives from operator-glued chains (`ls; rm -rf x`).

Both are exercised here, plus a representative sample of every pattern
the detector claims to catch. New patterns should add a positive case
AND a quoted-substring negative case.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "hooks"))

from pre_irreversible_inject import detect_bash  # noqa: E402


# ----- positives: things that should flag, one per supported pattern -----


def test_rm_short_flags():
    assert "rm with -r/-f flags" in detect_bash("rm -rf /tmp/foo")
    assert "rm with -r/-f flags" in detect_bash("rm -fR /tmp/foo")


def test_rm_long_flags():
    assert "rm with -r/-f flags" in detect_bash("rm --recursive /tmp/foo")
    assert "rm with -r/-f flags" in detect_bash("rm --force /tmp/foo")


def test_git_push_real():
    assert "git push (real, not dry-run)" in detect_bash("git push origin main")


def test_git_destructive_subcommands():
    assert "git reset --hard" in detect_bash("git reset --hard HEAD")
    assert "git commit --amend (rewrites history)" in detect_bash("git commit --amend")
    assert "git rebase" in detect_bash("git rebase main")
    assert "git branch -D (force-delete)" in detect_bash("git branch -D feature")
    assert "git clean -f" in detect_bash("git clean -fd")


def test_sudo_flags_both_labels():
    """`sudo rm -rf` should flag BOTH sudo AND rm-rf — sudo is recursive."""
    labels = detect_bash("sudo rm -rf /etc")
    assert "sudo (privileged execution)" in labels
    assert "rm with -r/-f flags" in labels


def test_curl_mutating():
    assert "curl with mutating verb" in detect_bash("curl -X POST https://example.com")
    assert "curl with mutating verb" in detect_bash("curl -XDELETE https://example.com")
    assert "curl with --data (POST-shaped)" in detect_bash('curl -d "k=v" https://example.com')


def test_psql_mutating_sql():
    assert "psql mutating SQL" in detect_bash('psql -c "DROP TABLE users"')
    assert "psql mutating SQL" in detect_bash('psql -c "delete from users"')


def test_kubectl_destructive():
    assert "kubectl mutating command" in detect_bash("kubectl delete pod foo")


def test_systemctl_split():
    """Separate labels for system-wide vs --user systemctl."""
    assert "systemctl service control" in detect_bash("systemctl stop nginx")
    assert "systemctl --user service control" in detect_bash("systemctl --user stop nginx")


def test_docker_destructive():
    assert "docker destructive command" in detect_bash("docker rm container")
    assert "docker destructive command" in detect_bash("docker stop container")


def test_aws_action_pattern():
    assert "aws mutating command" in detect_bash("aws s3api delete-bucket --bucket foo")


def test_gcloud_deep_command_shape():
    """Real gcloud commands have variable depth: the verb isn't always rest[1].
    Regression for a refactor bug that pinned the verb to rest[1] only."""
    assert "gcloud mutating command" in detect_bash("gcloud compute instances delete foo")
    assert "gcloud mutating command" in detect_bash("gcloud sql databases create mydb --instance=x")


def test_npm_publish():
    assert "npm publish" in detect_bash("npm publish")


def test_pip_install():
    assert "pip install/uninstall (real)" in detect_bash("pip install requests")


def test_dd_disk_write():
    assert "dd (raw disk write)" in detect_bash("dd if=/dev/zero of=/dev/sda bs=1M")


def test_redirect_block_device():
    assert "redirection to block device" in detect_bash("echo x > /dev/sda")


# ----- negatives: things that look dangerous but aren't -----


def test_rm_without_flags():
    assert detect_bash("rm foo.txt") == []


def test_git_push_dry_run():
    assert detect_bash("git push origin main --dry-run") == []


def test_git_rebase_abort_continue():
    assert detect_bash("git rebase --abort") == []
    assert detect_bash("git rebase --continue") == []


def test_pip_install_dry_run():
    assert detect_bash("pip install --dry-run requests") == []


# ----- false-positive class: dangerous strings inside quoted args -----


def test_quoted_git_push_in_grep():
    """grep'ing for the literal string `git push` should not flag."""
    assert detect_bash('grep "git push" notes.txt') == []


def test_quoted_rm_rf_in_echo():
    assert detect_bash('echo "rm -rf would be bad"') == []


def test_quoted_sudo_in_grep():
    assert detect_bash('cat file | grep "sudo"') == ["curl with --data (POST-shaped)"] or \
        "sudo (privileged execution)" not in detect_bash('cat file | grep "sudo"')


# ----- chained commands: operators must split segments -----


def test_chained_and_push():
    """`git pull && git push` — push is the second segment, must still flag."""
    assert "git push (real, not dry-run)" in detect_bash("git pull && git push")


def test_chained_semicolon_glued():
    """`ls; rm -rf x` (no space before `;`) — shlex.split would miss this;
    shlex.shlex with punctuation_chars catches it. Regression for the
    refactor's first attempt."""
    assert "rm with -r/-f flags" in detect_bash("ls; rm -rf /tmp/x")


def test_chained_pipe_no_space():
    """`cmd1|cmd2` — same shape as above."""
    assert "git push (real, not dry-run)" in detect_bash("echo done|git push")


# ----- robustness: malformed input must not crash -----


def test_unbalanced_quotes_returns_empty():
    """Unparseable shell — return [] rather than crashing or false-flagging."""
    assert detect_bash('echo "unterminated') == []
