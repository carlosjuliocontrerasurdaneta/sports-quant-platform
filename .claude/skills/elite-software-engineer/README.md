# Elite Software Engineer Skill for Claude Code

Production-oriented Claude Code Skill for repository analysis, design, implementation, testing, security review, performance review, debugging, refactoring, and code review.

## Structure

```text
elite-software-engineer/
├── SKILL.md
├── references/
├── templates/
├── scripts/
└── examples/
```

## Install

Copy the folder into one of these locations:

```bash
# User-level skill
mkdir -p ~/.claude/skills
cp -R elite-software-engineer ~/.claude/skills/

# Project-level skill
mkdir -p .claude/skills
cp -R elite-software-engineer .claude/skills/
```

Then use Claude Code normally. The skill should trigger for non-trivial software engineering tasks.

## Optional helper

```bash
python ~/.claude/skills/elite-software-engineer/scripts/repo_snapshot.py .
```

## Suggested prompts

```text
Use the elite-software-engineer skill to analyze this repo and implement X.
Review this PR like a staff engineer.
Debug this failing test and add regression coverage.
Refactor this module without changing behavior.
Perform a security review of this endpoint.
```
