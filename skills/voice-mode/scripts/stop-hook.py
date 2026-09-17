"""Claude Code Stop hook: speaks the latest assistant response via edge-tts.

Triggered after every assistant turn. Reads transcript path from stdin JSON,
extracts the last assistant text, cleans markdown for TTS, and fires a
background speak.py process.

Kills any in-flight ffplay before starting new speech so old audio doesn't
overlap with new responses.

Disable temporarily: set SPEAK_OFF=1 in the environment. Disable persistently:
delete the `.tts-enabled` marker file next to this script (see the voice-mode
SKILL.md for the toggle commands).
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SPEAK_PY = SCRIPT_DIR / "speak.py"
TTS_ENABLED_MARKER = SCRIPT_DIR / ".tts-enabled"  # exists -> TTS on, absent -> TTS off
MAX_CHARS = 8000  # safety cap — user can interrupt by speaking


def clean_markdown(text: str) -> str:
    """Strip markdown noise that reads poorly via TTS."""
    # Drop fenced code blocks entirely.
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # Drop inline code backticks but keep contents.
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Convert markdown tables to comma-separated speech-friendly lines.
    result_lines = []
    for line in text.splitlines():
        s = line.strip()
        if set(s) <= set("-|: "):  # separator row — skip
            continue
        elif s.startswith("|"):  # data row — join cells with comma
            cells = [c.strip() for c in s.strip("|").split("|") if c.strip()]
            result_lines.append(", ".join(cells))
        else:
            result_lines.append(line)
    text = "\n".join(result_lines)
    # Headers: drop the leading hashes.
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Bold/italic markers.
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    # Links: [label](url) -> label
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Bare URLs: drop entirely.
    text = re.sub(r"https?://\S+", "", text)
    # Bullet markers at start of line.
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
    # Numbered list markers.
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    # Collapse runs of blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_last_assistant_text(transcript_path: str) -> str:
    """Read JSONL transcript, return concatenated text of last assistant turn."""
    if not transcript_path or not os.path.exists(transcript_path):
        return ""

    last_assistant = None
    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Claude Code transcript entries usually nest the message under "message".
            inner = msg.get("message", msg)
            role = inner.get("role") or msg.get("type")
            if role == "assistant":
                last_assistant = inner

    if not last_assistant:
        return ""

    content = last_assistant.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return ""


# Our own playback process. Everything else counts as "someone else is using the
# speakers", which is the whole point of the check below.
OWN_PLAYER = "ffplay.exe" if os.name == "nt" else "ffplay"


def other_audio_playing() -> bool:
    """True when another app is actively playing sound (Windows only).

    Useful if you take calls or watch video at the same machine — speaking a
    reply over a live call or video is worse than staying quiet. Windows
    reports state 1 for an audio session that is actually rendering, which is
    why an idle-but-open app (state 0) does not count.

    Fails OPEN on purpose: if the check itself breaks (missing pycaw, or a
    non-Windows OS), TTS still speaks. A silent assistant that cannot explain
    itself is harder to debug than one that occasionally talks over something.
    """
    if os.name != "nt":
        return False
    try:
        from pycaw.pycaw import AudioUtilities
    except Exception:
        return False
    try:
        for session in AudioUtilities.GetAllSessions():
            proc = session.Process
            if not proc:
                continue
            if proc.name().lower() == OWN_PLAYER.lower():
                continue
            if session.State == 1:  # AudioSessionStateActive
                return True
    except Exception:
        return False
    return False


def kill_in_flight_audio() -> None:
    """Stop any currently-playing ffplay so we don't overlap audio."""
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/IM", "ffplay.exe"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            subprocess.run(["pkill", "ffplay"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except Exception:
        pass


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    transcript_path = payload.get("transcript_path", "")

    # Retry up to 3 times with a short sleep — the transcript flush may lag the hook.
    text = ""
    for attempt in range(3):
        text = extract_last_assistant_text(transcript_path)
        text = clean_markdown(text)
        if text:
            break
        if attempt < 2:
            time.sleep(0.25)

    if not text:
        return 0

    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS].rsplit(" ", 1)[0]

    # Local TTS - only if marker file present.
    # The marker may also SCOPE which sessions speak: if it contains any session
    # ids (one per line), only those sessions speak. An empty marker means all of
    # them, which is the default behaviour. Without this, enabling TTS made every
    # running Claude session talk at once.
    if not TTS_ENABLED_MARKER.exists():
        return 0
    try:
        allowed = [ln.strip() for ln in TTS_ENABLED_MARKER.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except Exception:
        allowed = []
    if allowed and not any(sid in transcript_path for sid in allowed):
        return 0
    if os.environ.get("SPEAK_OFF") == "1":
        return 0

    # Stand down if anything else is using the speakers - a call, a video, music.
    if other_audio_playing():
        return 0

    kill_in_flight_audio()

    # Fire-and-forget: don't block Claude Code's next turn on TTS playback.
    proc = subprocess.Popen(
        [sys.executable, str(SPEAK_PY)],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    proc.stdin.write(text.encode("utf-8"))
    proc.stdin.close()
    # Intentionally don't wait — speak.py runs to completion in its own group.

    return 0


if __name__ == "__main__":
    sys.exit(main())
