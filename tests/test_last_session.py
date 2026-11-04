"""Tests for remembered coding-agent session ids under /tmp."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cli.last_session import (
    agent_args_request_session,
    clear_last_session,
    extract_session_from_agent_args,
    parse_session_id,
    read_last_session,
    remember_last_session,
    resume_args_for_agent,
)


def test_remember_and_read_last_session(tmp_path):
    directory = str(tmp_path / "sessions")
    assert read_last_session("dev-a", directory=directory) is None
    remember_last_session("dev-a", "ses_abc", agent_type="opencode", directory=directory)
    assert read_last_session("dev-a", directory=directory) == ("ses_abc", "opencode")
    remember_last_session(
        "dev-a",
        "7b0ada27-f52d-4e43-b746-2ebf2074a462",
        agent_type="claude",
        directory=directory,
    )
    assert read_last_session("dev-a", directory=directory) == (
        "7b0ada27-f52d-4e43-b746-2ebf2074a462",
        "claude",
    )


def test_clear_last_session(tmp_path):
    directory = str(tmp_path / "sessions")
    remember_last_session("dev-a", "ses_1", agent_type="opencode", directory=directory)
    remember_last_session("dev-b", "ses_2", agent_type="opencode", directory=directory)
    clear_last_session("dev-a", directory=directory)
    assert read_last_session("dev-a", directory=directory) is None
    assert read_last_session("dev-b", directory=directory) == ("ses_2", "opencode")
    clear_last_session(directory=directory)
    assert read_last_session("dev-b", directory=directory) is None


def test_parse_session_id_from_agent_banners():
    claude = "Resume this session with: claude --resume=7b0ada27-f52d-4e43-b746-2ebf2074a462\n"
    assert parse_session_id(claude) == "7b0ada27-f52d-4e43-b746-2ebf2074a462"

    opencode = "Continue  opencode --mini -s ses_4f2a1c9bdeadbeef\n"
    assert parse_session_id(opencode) == "ses_4f2a1c9bdeadbeef"

    cursor = "To continue: agent --resume thread_abc123xyz\n"
    assert parse_session_id(cursor) == "thread_abc123xyz"

    # ANSI / CR noise from script(1)
    noisy = "\x1b[32mContinue\x1b[0m opencode -s ses_ansi123\r\n"
    assert parse_session_id(noisy) == "ses_ansi123"


def test_extract_and_detect_session_flags():
    assert extract_session_from_agent_args(["--session", "ses_1"]) == "ses_1"
    assert extract_session_from_agent_args(["--resume=abc-def"]) == "abc-def"
    assert extract_session_from_agent_args(["--prompt", "hi"]) is None
    assert agent_args_request_session(["--continue"]) is True
    assert agent_args_request_session(["-c"]) is True
    assert agent_args_request_session(["--resume"]) is True
    assert agent_args_request_session(["--prompt", "x"]) is False


def test_resume_args_for_agent():
    assert resume_args_for_agent("opencode", "ses_1") == ["--session", "ses_1"]
    assert resume_args_for_agent("claude", "uuid-1") == ["--resume", "uuid-1"]
    assert resume_args_for_agent("cursor", "thread-1") == ["--resume", "thread-1"]
