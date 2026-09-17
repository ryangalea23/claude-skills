---
name: voice-mode
description: Use when the user asks to enable/disable voice mode, turn text-to-speech on or off, or hear Claude's responses spoken aloud instead of just reading text.
allowed-tools:
  - Bash
---

# Voice Mode (text-to-speech for Claude Code)

## Overview

A Claude Code Stop hook can read each of Claude's responses aloud using `edge-tts` (free, no API key). This skill toggles that on and off with a marker file, so you don't need to edit settings or restart anything just to mute it.

**Privacy:** `edge-tts` is Microsoft's online text-to-speech service. While voice mode is on, the text of every Claude reply is sent over the network to Microsoft to be turned into audio. Leave it off in sessions where replies may contain secrets or anything you don't want leaving your machine.

This skill does NOT install anything - it assumes the pieces below are already set up (see Setup below). It just flips the switch.

## When to Use

**Enable** when the user says "turn on voice mode", "enable TTS", "read your replies out loud", or asks to hear responses spoken.

**Disable** when the user says "turn off voice mode", "disable TTS", "stop talking", or "go back to text".

**Don't use for:**
- Installing/configuring TTS from scratch - see Setup below, but assume it's installed once you're using this skill day to day.
- Adjusting voice quality/settings - change the `SPEAK_VOICE` environment variable instead (see table below).

## Quick Reference

| Action | Marker file |
|---|---|
| Enable | create `.tts-enabled` next to `stop-hook.py` |
| Disable | delete `.tts-enabled` next to `stop-hook.py` |
| Status | check whether the marker file exists |

The marker file lives in the same folder as `stop-hook.py` (`scripts/` in this skill folder, or wherever you installed it).

## Enable

```bash
touch /path/to/scripts/.tts-enabled
```

On Windows PowerShell:
```powershell
New-Item -ItemType File -Path "C:\path\to\scripts\.tts-enabled" -Force | Out-Null
```

Then test the voice directly, independent of the hook:
```bash
echo "Voice test." | python /path/to/scripts/speak.py
```

**Heads-up to surface:** the Stop hook only loads at Claude Code session start. If voice mode was enabled mid-session, tell the user to restart Claude Code for the hook to actually fire on responses. The manual `speak.py` test above still works without a restart.

## Disable

```bash
rm -f /path/to/scripts/.tts-enabled
```

On Windows PowerShell:
```powershell
Remove-Item "C:\path\to\scripts\.tts-enabled" -ErrorAction SilentlyContinue
```

Also stop any speech in progress:
```powershell
Stop-Process -Name ffplay -Force -ErrorAction SilentlyContinue
```
```bash
pkill ffplay 2>/dev/null || true
```

## Status

```bash
test -f /path/to/scripts/.tts-enabled && echo "TTS enabled" || echo "TTS disabled"
```

## Response Style While Voice Mode Is On

When TTS is active, Claude's responses get spoken aloud. Optimize for listening:
- Short prose, no markdown tables
- Lead with the answer or recommendation
- One question per turn, clearly phrased
- Spell out numbers when ambiguous ("eleven a.m." reads better than "11am")
- `stop-hook.py` strips most markdown before speaking, but keeping replies clean helps anyway

## Common Mistakes

| Mistake | Fix |
|---|---|
| Enabled mid-session, hook didn't fire | Hooks load at session start. Tell the user to restart Claude Code. |
| Voice sounds wrong | Set the `SPEAK_VOICE` environment variable. Options include `en-US-AriaNeural` (default), `en-US-JennyNeural`, `en-US-GuyNeural`, `en-US-AndrewNeural` - any `edge-tts` voice name works. |
| Speech overlaps between turns | `stop-hook.py` kills any in-flight player before starting new speech; if it still overlaps, check that only one Stop hook instance is registered. |

## Setup (one time, not part of normal use)

1. Install the Python packages: `pip install --user edge-tts`. `pip install --user pycaw` is optional - it lets the hook detect whether you're on a call or playing audio in another app and stay quiet if so; without it, TTS always speaks.
2. Make sure a media player is available for playback. The scripts default to `ffplay` (part of ffmpeg) via the `FFPLAY_PATH` environment variable (default `ffplay`, or set it to a full path like `C:\ffmpeg\bin\ffplay.exe` on Windows). Any command-line player that can take a file path works if you adjust `speak.py`'s `play()` function.
3. Copy `scripts/speak.py` and `scripts/stop-hook.py` from this skill folder to wherever you keep Claude Code scripts.
4. Register the Stop hook in your Claude Code `settings.json`:
   ```json
   "hooks": {
     "Stop": [
       { "hooks": [ { "type": "command", "command": "python /path/to/scripts/stop-hook.py" } ] }
     ]
   }
   ```
5. Test with `echo "hello" | python /path/to/scripts/speak.py` before wiring up the hook, to confirm playback works on your machine.

## Why This Setup (Reasoning History)

`edge-tts` was picked over paid TTS APIs because it's free and has no API key to manage. A Stop hook was picked over an MCP tool because it fires automatically after every response with zero extra typing. The marker-file toggle exists so you can mute Claude mid-session without touching `settings.json` or restarting.

If you want TTS to also route through a specific playback device (for example, streaming your desktop's audio to a phone or another room), that's a platform-specific extension on top of this skill - this skill only covers turning speech on and off.
