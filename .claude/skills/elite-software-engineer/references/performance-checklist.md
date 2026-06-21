# Performance Checklist

Use for loops, queries, APIs, data processing, rendering, caching, background jobs, and latency-sensitive paths.

## Check

- Algorithmic complexity.
- Query count and N+1 risks.
- Index usage.
- Network round trips.
- Serialization/deserialization cost.
- Memory growth.
- Streaming vs buffering.
- Pagination/batching.
- Cache correctness and invalidation.
- Lock contention.
- Hot path allocations.
- Startup/build-time impact.

## Output

```markdown
## Performance Review

Expected impact:
Hot paths affected:
Findings:
Mitigations:
Remaining risks:
```
