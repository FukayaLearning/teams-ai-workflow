---
name: teams-workflow
description: Process OneDrive Teams message queues, triage consultations and tasks using local LM Studio Decision models, manage SQLite tasks, and refine/copy consultation replies. Use when the user asks to check Teams messages, list/update Teams tasks, review consultations, or schedule Teams queue processing via Cron.
allowed-tools: Bash(python:*), Bash(python3:*)
license: MIT
compatibility: Requires Python 3.10+ and local SQLite / LM Studio configuration.
metadata:
  author: teams-ai-workflow
  version: "1.0"
---

# Teams AI Workflow Skill (Hermes Agent Hybrid Integration)

This skill connects **Hermes Agent** to the local `teams-ai-workflow` CLI (`python -m app.cli`).
It enables both **scheduled background triage (via Hermes Cron)** and **interactive task & consultation management** without wasting LLM context tokens on empty polling loops.

---

## Available CLI Commands

Always run commands from the repository root (`/home/sweet/workspace/teams-ai-workflow` or project directory) with `--json` for structured output:

### 1. Process Incoming Teams Queue (One-Shot)
Scans `TeamsQueue/incoming/` for new JSON files synced by OneDrive, evaluates relevance/intent via the local Decision Engine, saves to SQLite (`teams_workflow.db`), triggers desktop notifications/clipboard copy, and moves processed files to `processed/`.

```bash
python -m app.cli process-queue --json
```
- **Zero-Token Idle Efficiency**: If `incoming/` has no new files, this command exits immediately with `"scanned_files": 0` without calling the LLM.

### 2. List Tasks
Retrieve tasks extracted from Teams messages stored in SQLite (`tasks` table).

```bash
# List all pending (todo) tasks
python -m app.cli list-tasks --status todo --json

# List all tasks regardless of status (todo / in_progress / done)
python -m app.cli list-tasks --json
```

### 3. Update Task Status
Mark a task as `in_progress`, `done`, or back to `todo`.

```bash
python -m app.cli update-task <task_id> --status done --json
```

### 4. List Consultations & Suggested Replies
Inspect recent technical consultations/questions received on Teams, including identified missing information (`missing_points`) and the generated reply draft (`suggested_reply`).

```bash
python -m app.cli list-consultations --limit 20 --json
```

### 5. Copy or Refine Consultation Reply
Copy a consultation's suggested reply to the OS clipboard, or update it with a refined message drafted during conversation with the user and copy it immediately.

```bash
# Copy existing suggested reply for a message_id
python -m app.cli copy-reply "<message_id>" --json

# Save and copy a refined reply text
python -m app.cli copy-reply "<message_id>" --text "<refined_reply_text>" --json
```

---

## Workflows for Hermes Agent

### Workflow A: Interactive Task & Consultation Assistant
1. **When the user asks "未完了のTeamsタスクを見せて" or "今日来た相談は？"**:
   - Run `python -m app.cli process-queue --json` first if they want the latest synced messages included.
   - Run `python -m app.cli list-tasks --status todo --json` or `python -m app.cli list-consultations --json`.
   - Present a clean summary in Japanese.
2. **When the user asks to refine a reply (e.g., "山田さんへの返信案をもっと丁寧にしてクリップボードに入れて")**:
   - Fetch the consultation via `list-consultations --json`.
   - Draft the improved reply based on the user's instructions (and any local documentation/memory).
   - Run `python -m app.cli copy-reply "<message_id>" --text "<new_reply>" --json` so the user can immediately press `Ctrl + V` in Microsoft Teams.
3. **When the user finishes a task (e.g., "タスクID 3 を完了にして")**:
   - Run `python -m app.cli update-task 3 --status done --json` and confirm completion.

### Workflow B: Hermes Cron Automation
When the user asks to automate or schedule Teams queue monitoring in Hermes Agent:
- Configure a recurring job or script trigger that runs:
  ```bash
  python -m app.cli process-queue --json
  ```
- Because `process-queue` handles file moving, deduplication, LM Studio inference, SQLite persistence, and Windows notifications internally, Cron executions remain fast, deterministic, and token-efficient.

