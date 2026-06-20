# Smart-Agents
![Smart-Agents banner](./assets/smart-agents-banner.svg)

A Claude Code plugin marketplace. It hosts **feature-pipeline** — a four-stage,
multi-agent pipeline that takes a feature request and runs
plan → implement → test → review, pausing for you at the right moments.

## What's inside the pipeline

| Component | Stage | Model | Role |
|-----------|-------|-------|------|
| `planner` agent  | 1 | opus   | Turns a feature request into a tight spec at `.pipeline/spec.md`. Read-only on code. |
| `coder` agent    | 2 | sonnet | Implements the spec, summarizes changes to `.pipeline/changes.md`. |
| `tester` agent   | 3 | sonnet | Writes and runs tests, records results to `.pipeline/test-results.md`. |
| `reviewer` agent | 4 | opus   | Read-only final review; writes a SHIP / NEEDS WORK / BLOCK verdict to `.pipeline/review.md`. |
| ` /feature-pipeline:ship` command  | — | —      | Orchestrates all four stages in order, with stops for OPEN QUESTIONS and test failures. |

The agents hand work to each other through files in a `.pipeline/` directory.

## How to use it (step by step)

You need **Claude Code** installed. The pipeline runs through its `/plugin` and
subagent features.

**Step 1 — Add the marketplace (once per machine).**
Open Claude Code in any project and run:

```
/plugin marketplace add JimmyChen02/Smart-Agents
```

This registers the marketplace. Nothing is installed yet.

**Step 2 — Install the plugin (once per machine).**

```
/plugin install feature-pipeline
```

If asked which marketplace, choose `feature-pipeline-marketplace`. The four
agents and the `/ship` command are now available in **every** project on your
machine.

**Step 3 — Run the pipeline (any project, any time).**

```
/ship <describe the feature you want>
```

For example:

```
 /feature-pipeline:ship add a rate limiter to the public API
```

`/feature-pipeline:ship` clears stale handoff files, then runs the four stages in order:

1. **planner** writes a spec — pauses to show you any open questions.
2. **coder** implements the spec.
3. **tester** writes and runs tests — pauses if any fail.
4. **reviewer** does a read-only pass and prints a SHIP / NEEDS WORK / BLOCK verdict.

It does **not** merge anything — it leaves the work for you to review.

**Step 4 — One-time housekeeping per project.**
Add `.pipeline/` to the project's `.gitignore` so the agents' handoff files
aren't committed.

### Running a single agent

You don't have to run the whole pipeline. To use just one stage, ask for it by
name, e.g.:

```
Use the reviewer subagent to look at my current changes
```

### Getting updates

When a new version is published, pick it up with:

```
/plugin marketplace update feature-pipeline-marketplace
```

## Repo layout

```
.claude-plugin/marketplace.json     ← marketplace listing
plugins/feature-pipeline/           ← the plugin
  .claude-plugin/plugin.json
  agents/   planner, coder, tester, reviewer
  commands/ ship.md
```
