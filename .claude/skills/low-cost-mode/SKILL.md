---
name: low-cost-mode
description: Aggressively optimize value-per-token while maintaining correctness, safety, and task completion quality.
---

# LOW-COST MODE

## Mission

Maximize:

Value Delivered / Cost Consumed

Cost includes:
- Tokens
- Tool calls
- Repository exploration
- Subagents
- Verification overhead
- Iterations

## Activation

Automatically activate when:
- User requests speed
- User requests low cost
- Small bug fixes
- Small feature additions
- Documentation edits
- Refactors under 50 LOC

## Core Rules

### 1. Minimal Change
Prefer the smallest viable modification.

### 2. Incremental Context
Read only what is needed.
Expand only when required.

### 3. No Speculative Work
Do not improve unrelated code.
Do not optimize unless requested.

### 4. Compact Planning
Maximum 5 steps.

### 5. Single Solution Bias
Choose the highest-probability solution.
Implement first.
Explore alternatives only after failure.

### 6. Reuse Before Creation
Search existing code before writing new code.

### 7. Tool Budgeting
Use the minimum number of tools required.

### 8. Verification Economy
Run the narrowest verification capable of proving correctness.

### 9. Compact Output
Respond using:

Problem
Change
Verification
Result

### 10. Stop When Done
Do not continue beyond scope.

## Cost Tiers

### Ultra Low
Conditions:
- One file
- Under 50 LOC
- Clear request

Behavior:
- No planning
- No subagents
- No architecture review
- No documentation

### Low
Conditions:
- Up to 10 files
- Under 500 LOC

Behavior:
- Brief plan
- Targeted verification

### Standard Escalation
Escalate when:
- Security
- Authentication
- Infrastructure
- Database schema
- Ambiguous requirements
- More than 10 files

Message:

Task exceeds Low-Cost Mode operating boundaries. Recommend Standard Mode.

## Subagent Policy

Default: Disabled

Enable only when:
- Large codebase analysis
- Multi-domain investigation
- Explicit user request

## MCP Policy

Use MCP tools only when:
- Required to complete task
- No cheaper local alternative exists

## Repository Exploration Policy

Forbidden:
- Full repository scans
- Broad exploratory reading

Required:
- Targeted file discovery
- Progressive expansion

## Success Metric

High correctness
+
Low cost
+
Low iteration count
=
Success
