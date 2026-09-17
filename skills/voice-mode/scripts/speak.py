"""TTS script: takes text via stdin or argv, synthesizes via edge-tts, plays via ffplay.

Usage:
    echo "hello world" | python speak.py
    python speak.py "hello world"

Env overrides:
    SPEAK_VOICE   default: en-US-AriaNeural (warm female)
    SPEAK_RATE    default: +15% (slightly faster than normal)
    FFPLAY_PATH   default: ffplay (assumes it's on PATH; set a full path on Windows if not)
"""

import asyncio
import os
import subprocess
import sys
import tempfile

import edge_tts

VOICE = os.environ.get("SPEAK_VOICE", "en-US-AriaNeural")
RATE = os.environ.get("SPEAK_RATE", "+15%")
FFPLAY = os.environ.get("FFPLAY_PATH", "ffplay")


async def synth(text: str, out_path: str) -> None:
    communicate = edge_tts.Communicate(text=text, voice=VOICE, rate=RATE)
    await communicate.save(out_path)


def play(path: str) -> None:
    subprocess.run(
        [FFPLAY, "-nodisp", "-autoexit", "-loglevel", "quiet", path],
        check=False,
    )


def main() -> int:
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = sys.stdin.read()

    text = text.strip()
    if not text:
        return 0

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        out_path = f.name

    try:
        asyncio.run(synth(text, out_path))
        play(out_path)
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
