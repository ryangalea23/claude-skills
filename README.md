# claude-skills

Five Claude Code skills for personal productivity: notes, tasks, call transcription, text-to-speech, and PDF signing.

## Install

Each skill is a self-contained folder. Copy the ones you want into `~/.claude/skills/`:

```bash
cp -r skills/notes ~/.claude/skills/
cp -r skills/tasks ~/.claude/skills/
cp -r skills/transcribe ~/.claude/skills/
cp -r skills/voice-mode ~/.claude/skills/
cp -r skills/sign-pdf ~/.claude/skills/
```

Restart Claude Code (or start a new session) so it picks up the new skills. Each skill's `SKILL.md` has a `Setup` or `Requirements` section — read that before first use, especially for `voice-mode` and `sign-pdf`, which need a one-time setup step.

**Tested on:** Windows 11 with PowerShell and Git Bash. The Python scripts (`sign-pdf`, `voice-mode`) should work on macOS/Linux too, but only the Windows path has been run end to end. `notes`, `tasks`, and `transcribe` are plain markdown + Bash/curl and should be platform-neutral.

## Skills

### notes

Capture and search meeting notes, ideas, and facts as individual markdown files with frontmatter. Search runs with `ripgrep` across your notes folder.

**Needs:** `rg` (ripgrep) on PATH. Optional: a calendar-reading MCP tool, to prefill meeting attendees automatically.

### tasks

A personal task list in one markdown file (`tasks.md`), with tags, priority, due dates, and recurring tasks.

**Needs:** nothing beyond Claude Code itself. The shipped `tasks.md` is an empty template — start adding your own tasks.

### transcribe

Transcribe a local audio recording (mp3/m4a/wav) with OpenAI's Whisper API, then write a structured meeting note using the `notes` skill's format.

**Needs:** an `OPENAI_API_KEY` environment variable, `curl`, `jq` (or PowerShell for JSON parsing), and `ffmpeg` if you ever need to split a large file. This skill does not record audio for you — bring your own recording from whatever tool you use.

### voice-mode

Turn text-to-speech of Claude's replies on and off. A Claude Code Stop hook reads each response aloud with `edge-tts` (free, no API key) when a marker file is present.

**Needs:** `pip install edge-tts`, and `ffplay` (from ffmpeg) or another command-line audio player on PATH. Optional: `pip install pycaw` (Windows only) so the hook can detect when you're on a call and stay quiet. See the `Setup` section in `skills/voice-mode/SKILL.md` for the one-time hook registration in `settings.json`.

### sign-pdf

Stamp a signature image onto a PDF, either at detected AcroForm fields, near "Signature:"-style labels, or at explicit coordinates you pick from a rendered preview.

**Needs:** `pip install pymupdf pillow`, and your own signature image. `prep_signature.py` turns a photo or scan of your signature into a transparent PNG. **Never use anyone else's signature, and never commit a real signature image to a repo** — see the `.gitignore` in this repo and the Signature Asset Hygiene section in `skills/sign-pdf/SKILL.md`.

## License

MIT, see `LICENSE`.
