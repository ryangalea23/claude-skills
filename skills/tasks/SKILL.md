---
name: tasks
description: |
  Personal task list. Add, list, complete, search, and tag tasks. Storage is a single
  markdown file at ~/.claude/skills/tasks/tasks.md (the source of truth - read it before
  every operation). Tags use #word format (people: #alex, contexts: #1on1, projects:
  #acme-corp). Priority: !high / !med / !low. Due dates: due:YYYY-MM-DD.
  Use when asked to "add task", "add to my list", "remind me to", "what's on my list",
  "what's due", "tasks for [person]", "complete task", "what's on for today", "1:1 prep",
  "tasks for today's meetings", or invoked as /tasks. Also surfaces for natural phrases
  like "I should follow up with X" or "don't let me forget Y".
allowed-tools:
  - Read
  - Edit
  - Write
  - AskUserQuestion
---

# Tasks

Personal task list. Single markdown file at `~/.claude/skills/tasks/tasks.md`. **Read it before every operation** - it's the source of truth and the user can edit it directly outside of /tasks calls.

## File format

```markdown
# Tasks

## Open

- [ ] discuss onboarding timeline #sam #1on1 due:2026-05-09 created:2026-05-02
- [ ] send Q3 numbers to Alex #alex #board !high created:2026-05-02
- [ ] review mobile UI mockups #product (from email msg:19de8d8c3d955e9e) created:2026-05-02

## Done

- [x] (2026-05-01) approve sales contract #acme-corp #legal created:2026-04-15
```

**Conventions:**
- `#word` - tag (people: `#alex` `#sam`; contexts: `#1on1` `#board` `#product`; projects: `#acme-corp`)
- `!high` `!med` `!low` - priority (omit for normal)
- `due:YYYY-MM-DD` - due date (always absolute, never "Friday")
- **`created:YYYY-MM-DD` - creation date. Required on every new task.** Used for drift detection.
- **`repeat:Nd` - recurring task.** When completed, re-spawn in Open with `due:<completion+N>` and `created:<today>`. Use `7d` for weekly, `14d` biweekly, `30d` monthly-ish, `90d` quarterly. Useful for project check-ins ("Check in on the launch repeat:7d").
- `(from email msg:<id>)` - link back to an email thread when the task was captured during an email-triage workflow, if you have one
- Tags, priority, dates, repeat can appear anywhere in the line; the body text is everything else
- Done items are prefixed with `(YYYY-MM-DD)` showing completion date

**Example with recurring task:**
```
- [ ] Check in on the launch with Sam #acme-corp #sam repeat:7d due:2026-05-09 created:2026-05-02
- [ ] Review pipeline with the sales team #pipeline #1on1 repeat:7d due:2026-05-09 created:2026-05-02
- [ ] Q3 board prep #board repeat:90d due:2026-08-01 created:2026-05-02
```

## Procedure

### Always step 1: Read the file

```
Read ~/.claude/skills/tasks/tasks.md
```

If the file is empty or doesn't exist, create it with the template structure above (empty Open and Done sections).

### Adding a task

Triggered by: "add task", "add to my list", "remind me to", "I need to", "follow up with", "don't let me forget", or `/tasks add <text>`.

1. Parse the input for body text + any inline tags / priority / due date.
2. If the user mentions a person but doesn't tag them, ASK before adding ("Tag this for #sam?") - don't auto-tag based on guessing.
3. **If no due date is provided, always ask: "When is this due or when do you want to be reminded?"** Convert relative answers ("Friday", "next week") to absolute dates (`due:YYYY-MM-DD`) before saving. Today's date is in the system context. Only skip this if the task is clearly open-ended with no natural deadline (e.g. a standing reminder or recurring cadence task).
4. **Always append `created:<today's-date>`** in YYYY-MM-DD format. This is required for drift detection.
5. Append to the Open section using the `Edit` tool. Don't mess with order; new tasks go at the bottom of Open.
6. Confirm: *"Added: [body] [tags]"*. Brief.

### Listing tasks

Triggered by: `/tasks`, "what's on my list", "show me my tasks", "what's open".

1. Read the file. Number the Open tasks 1-N in display order (file order).
2. Show:
   ```
   1. [tags] body (due X) (priority)
   2. ...
   ```
3. End with: *"What next? Add, complete, or filter (e.g. 'for sam')."*

If many tasks, group by priority or by tag if it makes the table easier to scan. Keep it functional, not fancy.

### Calendar-aware surfacing (1:1 prep, today's meetings)

Triggered by: "what's on for today", "1:1 prep", "tasks for today's meetings", "what should I bring up with Sam at our 2pm".

This step needs a calendar tool wired up (an MCP server or similar that can list today's events). If you don't have one, skip it and just filter tasks by tag manually (see below).

1. Call your calendar tool for today's events.
2. For each event, extract candidate person tags from:
   - The event summary (e.g. "Sam 1:1" → `#sam`)
   - Attendee email addresses (firstname before `@` → `#firstname`)
3. Read tasks.md.
4. For each meeting in chronological order, list any Open tasks where ANY tag matches the candidate person tags. Format:
   ```
   9:00 AM - Sam 1:1
     1. discuss onboarding timeline
     2. roadmap follow-up after the offsite

   2:00 PM - Team sync (Taylor, Jordan)
     - no tagged tasks
   ```
5. If a meeting has no matching tasks, say so plainly (don't pad).
6. End with: *"Anything to add for today's meetings?"*

If the user asks about a specific upcoming meeting (not today), expand the time window. Default is today.

### Filtering by tag(s)

Triggered by: "what's on my list for sam", "tasks for #alex", "1:1 with sam what should I bring up", `/tasks for <tag>`.

1. Read the file.
2. Match Open tasks where ANY of the user-mentioned tags appear (OR semantics for single mentioned tag, AND for multi-tag like "for sam at 1:1" - match `#sam` AND `#1on1`).
3. Number the matches as a fresh list. If empty, say so.
4. End with: *"Anything to add for [person/context]?"*

### Completing a task

Triggered by: "complete 3", "done with 1", "mark task 2 done", "finished the contract one", `/tasks done <number>`.

1. Read the file.
2. Identify the task: by number (from the most recent listed view) or by body match if user describes it.
3. If ambiguous, ASK which one.
4. **Check for `repeat:Nd` annotation.** If present, this is a recurring task.
5. Use `Edit` to:
   - Remove the task line from Open
   - Add it to the TOP of Done with prefix `(YYYY-MM-DD)` and `[x]` checkbox
   - **If recurring:** also add a NEW line at the bottom of Open with the same body + tags + priority + repeat annotation, plus updated `due:<today+N days>` and `created:<today>`. Strip any old `due:` and `created:` from the new line and replace with fresh values. Strip `(from email msg:...)` annotations from the recurring copy (the email context is one-time, not relevant on recurrence).
6. Confirm: *"Completed: [body]"*. If recurring: *"Completed and respawned: next due [date]"*. Brief.

**Removing recurrence (stop the cycle):** if user says "stop repeating task 3" or "drop the repeat", edit the task line in place to remove the `repeat:Nd` annotation. The task continues as a one-off.

### Showing recurring tasks (cadence audit)

Triggered by: "show recurring", "what's on repeat", "audit my check-ins", "what cadences am I running", `/tasks recurring`.

1. Read the file.
2. Filter Open tasks where the line contains `repeat:` annotation.
3. Group by cadence (Weekly = 7d, Biweekly = 14d, Monthly = 30d, Quarterly = 90d, Other = anything else). Within each group, sort by next due date ascending.
4. Format:
   ```
   RECURRING CHECK-INS (N)

   Weekly (3)
   1. Check in on the launch with Sam #acme-corp #sam - next: 2026-05-09
   2. Pipeline review with sales team #pipeline - next: 2026-05-09
   3. EA sync #ea - next: 2026-05-09

   Monthly (1)
   4. NPS review #customer-success - next: 2026-06-02

   Quarterly (1)
   5. Q3 board prep #board - next: 2026-08-01
   ```
5. End with: *"Anything to add, remove, or change cadence?"*

The point of this view is to let the user audit their check-in commitments. If they see "Weekly check-in on a project that ended last month" they can drop it. If they see too many weeklies they can change cadence.

### Showing recent completions

Triggered by: "what did I complete this week", "show me what's done", `/tasks done`.

Read Done section, show top 10 (most recent first).

### Editing a task

Triggered by: "change task 2 to...", "add #alex to task 3", "set task 1 to !high".

Read, locate by number, Edit the line in place. Confirm.

### Removing a task without completing it

Triggered by: "remove task 2", "I don't need to do task 5 anymore", "drop task 3".

Locate by number. Use Edit to remove the line entirely (don't move to Done - Done is for completed work). Confirm: *"Removed: [body]"*.

## Tag conventions (recommended, not enforced)

Pick up whatever the user uses; suggest these patterns when it helps:

- **People**: `#firstname` lowercase (`#sam`, `#alex`, `#taylor`)
- **Contexts**: `#1on1`, `#board`, `#fundraising`, `#product`, `#hiring`, `#legal`
- **Projects**: whatever the user's own project shorthand is (`#acme-corp`, `#mobileapp`)

When the user adds a task and mentions a person, suggest tagging if not done. When they have many tasks for one person, that's probably a 1:1 list - the next agent run could surface those before that meeting (future enhancement).

## When to ASK vs DECIDE

- **Ask**: ambiguous task target ("complete the onboarding one" when there are two), unclear person tag, relative date that could mean multiple things
- **Decide**: clear-cut completions, obvious tag from context (user says "follow up with Alex on X" → `#alex` is fine to assume, but confirm at the end)

## Email integration (optional)

If this skill is invoked from inside an email-triage workflow ("add a task to follow up with Alex about this email"):

1. Capture the message_id from the current email being reviewed
2. Append to Open with `(from email msg:<message_id>)` annotation
3. The annotation lets future task reviews fetch the original email later, if you have a tool that can do that

When listing tasks tagged with email context, you can offer: *"Want me to pull the original email for #3?"*

## What this skill does NOT do

- No reminders / time-based notifications (pair with a scheduler skill for daily/weekly digests, if you have one)
- No external sync (Linear, Todoist, etc.) - markdown only
- No mobile capture - tasks have to be added via Claude Code session (or the user directly editing the file)
- No automatic prioritization - the user owns priority assignment
