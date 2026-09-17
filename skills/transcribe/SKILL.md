---
name: transcribe
description: |
  Transcribe a local audio recording and save it as a meeting note. Takes an
  audio file (mp3/m4a/wav), uploads to OpenAI Whisper, then produces a
  structured summary written via the `notes` skill schema in `~/work/notes/`.

  Default behavior: if no file given, picks the most recent recording in
  `~/work/recordings/`. Pairs with the `record-call` script in this skill's
  `scripts/` folder (Windows only).

  Use when asked to "transcribe this", "transcribe the recording", "summarize
  the call", "/transcribe", "what did we say on that call", or after running
  `record-call stop`.
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - AskUserQuestion
---

# Transcribe

Convert a local audio recording into a structured meeting note. Single-pass: Whisper API for the transcript, then synthesize the note inline using the `notes` skill's schema. This skill does not require any particular recording tool — bring your own recording (any tool that produces an mp3/m4a/wav file works). On Windows, `scripts/record-call.ps1` is included as an optional mic-only call recorder that pairs with it (see Recording with `record-call` below).

## Requirements

- An OpenAI API key with Whisper access, available as the environment variable `OPENAI_API_KEY`. How you load that variable into your shell (a `.env` file, your OS's secret manager, etc.) is up to you — this skill just expects it to already be set when Claude Code starts, or readable from a file you point it at.
- `curl` and `jq` (or PowerShell's JSON parsing) for calling the API and reading the response.
- `ffmpeg` on PATH if you ever need to chunk a large file (see step 3), or if you use `record-call` (see below).
- The `notes` skill installed alongside this one — transcribe writes into `~/work/notes/` using its filename and frontmatter format.

## Recording with `record-call` (optional, Windows only)

`scripts/record-call.ps1` starts and stops a mic-only ffmpeg recording in the background and drops finished files straight into the recordings folder this skill reads from. It does not capture system/call audio, only your microphone — so it captures your side of a call, not the other person's, unless your setup routes both into one input device.

```powershell
record-call start "team sync"   # -> ~/work/recordings/2026-05-21_140530_team-sync.mp3
record-call stop
record-call status
record-call list
record-call devices             # list audio input devices ffmpeg can see
```

Install: copy `record-call.ps1`, `record-call.cmd`, and `_record-guard.ps1` (from this skill's `scripts/` folder) to a folder on your PATH, keeping all three together — `record-call.cmd` is a thin wrapper so you can type `record-call` instead of the full PowerShell invocation, and `_record-guard.ps1` is a background helper `record-call.ps1` spawns, not something you run directly.

Env overrides:
- `RECORD_CALL_DIR` — recordings folder (default `~/work/recordings`, matching this skill's default).
- `RECORD_CALL_FFMPEG` — path to `ffmpeg.exe` if it's not on PATH.
- `RECORD_CALL_MIC` — a substring to match your preferred input device name (run `record-call devices` to see what's available). Without it, `record-call` just uses the first device it finds — set this if you have more than one microphone.

## Inputs

- **Audio file path** (optional). If absent, default to the newest `.mp3` / `.m4a` / `.wav` in `~/work/recordings/`.
- **Meeting context** (optional). User may pass a meeting name, title, or "for the Tuesday call". If absent, infer from the recording filename slug; if still unclear, ask.

## Hard rules

- **Never auto-save** before showing the proposed filename + frontmatter + summary preview and getting a "go". Same discipline as the `notes` skill.
- **Always use the `notes` schema** for the output file (frontmatter + filename format defined below). Don't invent a new layout.
- **Always confirm the meeting** if today's calendar has multiple events that could match — present a numbered list and ask. (This step needs a calendar tool wired up; skip it if you don't have one.)
- **Preserve the raw transcript.** Write it to `~/work/recordings/transcripts/<recording-stem>.txt` alongside the structured note. Useful later, cheap to keep.
- **Don't chunk silently.** If the file is >24 MB, tell the user, then split with ffmpeg into ≤20-minute chunks before uploading.

## Procedure

### 1. Resolve the audio file

- If user passed a path → use it. Confirm it exists.
- Else: `Glob ~/work/recordings/*.{mp3,m4a,wav}`, sort by mtime, pick newest. Tell the user which file you picked: *"Transcribing the latest: `2026-05-21_140530_team-sync.mp3` (12 min, 4.3 MB). Different file?"*

### 2. Pick / confirm the meeting

Parse the filename slug for hints (`team-sync`, `1on1-with-sam`, etc.) and, if you have a calendar tool wired up, check today's calendar for matching events.

Present matches:
```
Today's meetings near this recording:
1. 2:00 PM — Team sync (Taylor, Jordan)
2. 4:30 PM — Standup (Morgan, Casey)

Which meeting was this? (or 'none' to fill manually)
```

On a number: prefill `title`, `people`, suggested tags from attendee firstnames. On "none": ask the user for title + attendees.

### 3. Check file size and chunk if needed

```bash
size=$(stat -c%s "$file" 2>/dev/null || powershell -c "(Get-Item '$file').Length")
```

- ≤ 24 MB: upload as-is.
- > 24 MB: tell the user the file is too large for a single upload, then chunk with ffmpeg into 20-minute segments at the same encoding:
  ```
  ffmpeg -i "$file" -f segment -segment_time 1200 -c copy "$dir/chunk_%03d.mp3"
  ```
  Upload each chunk separately, concatenate transcripts in order with a `[chunk N]` marker between them.

### 4. Call Whisper

Read the API key from the `OPENAI_API_KEY` environment variable (or wherever your setup stores it):
```bash
key="$OPENAI_API_KEY"
```

Upload:
```bash
curl -s https://api.openai.com/v1/audio/transcriptions \
  -H "Authorization: Bearer $key" \
  -F file=@"$file" \
  -F model=whisper-1 \
  -F response_format=verbose_json \
  -F language=en
```

`verbose_json` gives us segments + timestamps. Parse with `jq` or PowerShell.

If the response is `Thanks for watching!` / Japanese / something obviously empty: warn the user the recording was likely silent (mic muted, wrong device, no audio).

### 5. Save the raw transcript

Write the full transcript text to:
```
~/work/recordings/transcripts/<recording-stem>.txt
```
With a small header (file, duration, model). Cheap insurance — never re-pay Whisper for the same file.

### 6. Synthesize the meeting note

Read the transcript inline (use the conversation, not a tool). Produce a structured summary in this shape:

```markdown
## Summary
1-3 sentence high-level. What was this call actually about?

## Key decisions
- ...

## Action items
- [ ] @who — what — by when (if mentioned)

## Open questions
- ...

## Raw transcript
See `~/work/recordings/transcripts/<stem>.txt`.
```

Tone: terse, bullet-heavy, no editorializing. If a section has nothing, omit it (don't write "N/A").

### 7. Confirm and write

Show the proposed:
- Filename (matching `notes` schema: `YYYY-MM-DD_meeting_<slug>.md`)
- Full frontmatter block
- The summary body

In one block, then ask: *"Save to `~/work/notes/2026-05-21_meeting_team-sync.md`? (y / edit / cancel)"*

On "y": `Write` the file. Confirm path back to user.
On "edit": ask what to change, redo from step 6.
On "cancel": don't write. The raw transcript at step 5 is still saved.

## Frontmatter

Match `notes` exactly:
```yaml
---
type: meeting
date: 2026-05-21
title: Team sync
tags: [#acme-corp, #taylor, #jordan]
people: [taylor, jordan]
source: recording:<absolute-path-to-mp3>
---
```

`source:` carries the recording path so the user can later trace back to the audio. The transcript file is also implied by the recording stem.

## When to ASK vs DECIDE

- **Ask:** which meeting (if multiple plausible matches today), missing attendees, ambiguous title.
- **Decide:** file picked from `latest` default, summary structure, tag suggestions from attendee firstnames (then confirm at step 7).

## What this skill does NOT do

- No system/call-audio capture — `record-call` is mic-only, so it gets your side of a call, not the other person's. Bring your own mp3/m4a/wav from another tool if you need both sides.
- No speaker diarization — a single-track recording only captures one side clearly unless your recording setup captures both.
- No automatic Slack/email forwarding of summaries — output is the meeting note file, full stop.
- No real-time transcription — strictly post-call.
- No re-transcription of the same file unless explicitly asked (the raw `.txt` from step 5 is the cache).
