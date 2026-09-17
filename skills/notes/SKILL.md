---
name: notes
description: |
  Capture and find notes. Three types: meeting (notes from a specific meeting),
  idea (something to think about later), fact (a tidbit to remember). All notes
  save to a notes folder (default `~/work/notes/`, see Storage below) with
  required frontmatter and consistent filenames so search actually works.
  Search runs across the whole notes root (notes, and anything else you keep
  under that same folder, like saved emails or briefs).
  Use when asked to "take a note", "note this", "save this idea", "save this fact",
  "meeting notes for...", "find my notes about...", "what did I write down about...",
  "show meeting notes", "show ideas", "show facts", or invoked as /notes.
  Also surfaces for natural phrases like "I should write this down" or "remind me of this".
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
  - AskUserQuestion
---

# Notes

Personal notes. Three types, all stored as individual markdown files with required frontmatter for findability.

## Storage

- **Root folder:** `~/work/notes/` by default. To use a different folder, set the environment variable `NOTES_DIR` before starting Claude Code, and swap `~/work/notes/` for `$NOTES_DIR` everywhere in this file.
- **Filename:** `YYYY-MM-DD_<type>_<topic-slug>.md`
  - Type is one of: `meeting`, `idea`, `fact`
  - Slug: lowercase, hyphens, no punctuation, max ~50 chars
  - Examples:
    - `2026-05-02_meeting_1on1-with-sam.md`
    - `2026-05-02_idea_notes-skill-design.md`
    - `2026-05-02_fact_supabase-rls-pattern.md`
- **Frontmatter (required, every note):**
  ```yaml
  ---
  type: meeting | idea | fact
  date: 2026-05-02
  title: short human title
  tags: [#sam, #acme-corp]        # optional, lowercase #word
  people: [sam, taylor]           # meeting notes only — short names, lowercase
  source: email msg:<id> | conversation | link:<url> | null
  ---
  ```
- **Body:** free-form markdown.

## Hard rules

- **Always include the full frontmatter block.** Missing fields make notes unfindable later.
- **Filename strict format.** `YYYY-MM-DD_<type>_<topic-slug>.md`. No exceptions. Date is today's date from the system context (absolute, never "today" / "Friday").
- **Type is one of three.** `meeting`, `idea`, `fact`. If the user is ambiguous, ASK. Don't invent a fourth type.
- **Don't auto-tag people.** If the user mentions a person without explicitly tagging, ask before adding `#person` (same pattern as `/tasks`).
- **Don't auto-create.** Confirm the parsed type, title, and tags inline before writing the file. One sentence is enough: *"Saving as fact note `2026-05-02_fact_supabase-rls-pattern.md` with tags `#supabase #postgres`. Go?"*

## Procedure

### Always step 1: Confirm or determine the type

Triggered by: "note this", "save this", "take a note", "meeting notes for X", "idea:", "fact:", "/notes <body>".

Parse the trigger:
- "meeting notes for X" / "from my meeting" → `meeting`
- "idea:" / "I just thought of" / "what if" → `idea`
- "fact:" / "save this:" / "tidbit:" / "remember that" → `fact`
- Ambiguous → ASK: "Meeting note, idea, or fact?"

### 2a. Capture a meeting note

1. If you have a calendar tool wired up (an MCP server that can list today's events), call it for today's events and present them as a numbered list with time + summary + attendees:
   ```
   Today's meetings:
   1. 9:00 AM — 1:1 with Sam (Sam)
   2. 11:00 AM — Acme Corp sync (Taylor, Jordan)
   3. 2:00 PM — Team standup (Morgan, Casey)

   Which meeting is this for? (or 'none')
   ```
   If no calendar tool is available, skip straight to asking for the meeting title and attendees.
2. **Wait for the user's pick.**
   - On a number: prefill `title` from event summary, `people` from the attendee firstnames (lowercase). Suggest tags from common patterns (e.g. attendee firstnames → `#firstname`).
   - On "none": ask for title + attendees manually.
3. Capture body. If the user gave the body inline ("meeting notes for the Sam 1:1: discussed onboarding..."), use that. Otherwise prompt: "What did you discuss?"
4. Confirm filename + frontmatter inline. Write with the `Write` tool.
5. Confirm path back: *"Saved: `~/work/notes/2026-05-02_meeting_1on1-with-sam.md`"*

### 2b. Capture an idea note

1. The body is usually inline ("idea: notes skill should also handle..."). Use everything after the trigger word as the body.
2. Generate a 2-4 word slug from the body (lowercase, hyphens). Show it: *"Slug: `notes-skill-search`. Different?"*
3. Suggest tags from obvious nouns/projects in the body. Confirm.
4. Write the file. Confirm path.

### 2c. Capture a fact note

Facts are the highest-value-to-find category. Push for tags.

1. Body is usually inline ("fact: postgres RLS policies cascade through views..."). Use everything after the trigger as body.
2. Ask for a topic slug if not obvious from the first sentence: *"Topic slug? (e.g. `postgres-rls-cascade`)"*
3. **Always ask for at least one tag.** Facts without tags rot. Suggest tags from the body's nouns; the user can accept or replace.
4. Write the file. Confirm path.

### 3. Find notes (search)

Triggered by: "find notes about X", "what did I write down about Y", "search my notes", "/notes find <query>".

**Default search scope is the entire notes root** (`~/work/notes/` or your `NOTES_DIR`, and any sibling folders you keep under the same parent, like saved emails or briefs). The user may want to find anything they've saved, not just notes.

1. Use ripgrep across the notes root:
   ```
   Bash: rg -i --type md -l "<query>" "$HOME/work/"
   ```
2. For each hit, also pull a one-line preview (first non-frontmatter line containing the match).
3. Present numbered:
   ```
   Hits (5):
   1. ~/work/notes/2026-05-02_fact_supabase-rls.md — "RLS policies cascade through views..."
   2. ~/work/notes/2026-04-28_meeting_1on1-with-sam.md — "discussed onboarding..."
   3. ~/work/email/saved/2026-04-15_taylor_q3-numbers.md — (subject line)
   ...
   ```
4. End with: *"Open a number to read it, or refine."*
5. On "open 1" / "1" → `Read` the file and surface contents.

**Filter flags** (optional, parse from query):
- `type:meeting` / `type:idea` / `type:fact` → restrict glob to `*_<type>_*.md` in `~/work/notes/`
- `since:YYYY-MM-DD` → filter results by filename date prefix
- `for:#tag` → grep for the tag in frontmatter or body
- `from:<sender>` → match email saves where frontmatter `from:` includes the value

### 4. List notes by type

Triggered by: "show meeting notes", "show ideas from this week", "show facts", "/notes list type:<t>".

1. Glob `~/work/notes/*_<type>_*.md`.
2. Apply date filter if given (`since:` or "this week" → past 7 days).
3. Sort by filename date descending.
4. Show numbered: date + title + tags.
5. End with: *"Open a number to read it."*

### 5. Facts view (browse by tag)

Triggered by: "show facts", "/notes facts", "what facts do I have about X".

Facts accumulate forever. This view groups them by tag for browsing.

1. Glob `~/work/notes/*_fact_*.md`.
2. For each, parse frontmatter `tags`.
3. Group by tag. A fact with multiple tags appears under each (don't dedupe — browsing benefit > listing tidiness).
4. Format:
   ```
   FACTS (12 total)

   #postgres (3)
   1. 2026-05-02 — RLS policies cascade through views
   2. 2026-04-30 — Window functions can't reference aliases in the same SELECT
   3. 2026-04-12 — pg_stat_statements needs preload

   #acme-corp (2)
   4. 2026-04-28 — They use Salesforce, not HubSpot
   5. 2026-03-15 — Decision-maker is the COO, not the CIO

   Untagged (1)
   6. 2026-04-01 — ...
   ```
5. End with: *"Open a number to read, or filter by tag."*

If a fact has no tags, group under `Untagged` and surface count prominently — that's a flag the user should fix.

### 6. Open / read a note

Triggered by: "open #N", "show me the X note", "read note 3".

`Read` the file. Surface its contents. Offer: *"Edit, append, or done?"*

### 7. Edit / append

Triggered by: "add to that note", "append:", "edit note 3".

`Read` then `Edit`. Same pattern as `/tasks`. For meeting notes especially, appending follow-ups is common ("discussed today: ..."). Just append below existing body, with a date subhead if the new content is from a different day:
```markdown
## 2026-05-09 follow-up
- Sam confirmed the timeline
- Need to circle back with Taylor
```

### 8. Delete a note

Triggered by: "delete note 3", "remove the X note".

Confirm exact filename + first line. On verbatim approval, delete the file. Don't move to a trash folder — the user has git history if they need recovery.

## Email integration (optional)

If you also use an email-triage workflow that can call this skill ("note from this email"):

1. The caller passes: type, sender (suggested tag), msg_id, subject, optional body snippet.
2. Set `source: email msg:<id>` in frontmatter.
3. Suggest the sender's firstname (or domain shortname) as a tag.
4. Body should include a 2-3 line quoted excerpt from the email + the user's own commentary.
5. Confirm and write.

This lets the user later `/notes find` and pull both the note and (via the `source:` link) the original email back, if you have a tool that can fetch email by id.

## When to ASK vs DECIDE

- **Ask:** ambiguous type (meeting vs idea vs fact), missing topic slug for a fact, person tags not explicit, "which meeting" for a meeting note.
- **Decide:** clear type from trigger word, slug obvious from body, tags only if the body literally says "#tag".

## What this skill does NOT do

- No automatic tagging based on guessing — the user's tags are the user's tags.
- No external sync (Notion, Obsidian, etc.) — markdown files only.
- No mobile capture — notes added via Claude Code session or by editing files directly.
- No auto-summarization of long notes — store what the user wrote.
- No reminders / time-based surfacing — pair with a scheduler skill for digests, if you have one.
- No index file (`NOTES.md`) — pure filename + frontmatter + grep. Indexes drift.
