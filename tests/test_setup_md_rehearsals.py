"""SETUP.md lines from the 14 Nov rehearsals (Alex in Claude Code, Marcus in Codex), approved by Sacha ("ok for a)")."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def setup_md():
    return (ROOT / "SETUP.md").read_text()


def section(title):
    return setup_md().split(f"## {title}", 1)[1].split("\n## ", 1)[0]


def test_the_address_is_asked_as_plain_text():
    # Claude Code offered "type a neighborhood" and "a landmark" as buttons; picking one sent no text, twice
    home = section("Describe your home")
    assert "Ask the address as plain chat text, with no options to pick, even with a question tool" in home
    assert "except the address question" in setup_md().split("## Get ready", 1)[0]


def test_profiles_are_numbers_where_the_tool_cant_pick_several():
    # Codex's question box picks one option: adding allergies took a second message
    home = section("Describe your home")
    assert "Without a question tool that picks several (Codex's picks one)" in home
    assert "Type the numbers, like 1 3, or none" in home


def test_the_page_opens_when_no_token_page_was_used():
    # Alex's token was already saved, so no tab turned into the home, and nothing opened it
    verify = section("Start and verify")
    assert "If the token was saved on its page in this session, the page where the user saved the token turns into the home by itself" in verify
    assert "Otherwise open the address once" in verify


def test_the_home_server_steps_without_offering_ssh():
    # Codex asked for the SSH address to copy the folder itself
    again = section("Use it again")
    assert "Don't offer to copy it over SSH" in again


def test_the_check_uses_the_address_the_app_printed():
    # Claude Code checked localhost:5555, which another server held, while the app ran elsewhere
    verify = section("Start and verify")
    assert "The app's address is on the first line of `app.log`" in verify
