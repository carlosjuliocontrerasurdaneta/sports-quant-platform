# Design Workflow

Use this for architecture, API, database, or multi-file changes.

## Steps

1. Identify the current architecture.
2. Locate existing extension points.
3. Define target behavior.
4. Propose at least two viable options when tradeoffs matter.
5. Recommend the smallest safe option.
6. Document migration and compatibility concerns.

## Design output

```markdown
## Design

### Current state
### Target behavior
### Option A
Pros:
Cons:

### Option B
Pros:
Cons:

### Recommended approach
### Compatibility
### Rollout plan
### Risks
```

## Decision rules

Prefer existing abstractions over new abstractions.

Add abstractions only when:
- There are at least two concrete call sites, or
- The domain concept is already stable, or
- The abstraction reduces a real risk.

Avoid speculative extensibility.
