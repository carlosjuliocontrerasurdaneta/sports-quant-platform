# Refactoring Workflow

Use this when the user asks to clean up, simplify, reorganize, modularize, or reduce technical debt.

## Constraints

A refactor must preserve observable behavior unless explicitly requested otherwise.

## Process

1. Identify current behavior.
2. Identify pain points.
3. Define refactor goal.
4. Add or verify characterization tests.
5. Refactor incrementally.
6. Run tests after meaningful steps.
7. Document remaining debt.

## Safe refactor patterns

- Extract function
- Extract class/module
- Rename for clarity
- Replace duplication with shared utility
- Replace conditionals with table-driven logic where appropriate
- Split large functions by responsibility
- Isolate side effects

## Avoid

- Combining behavior change with refactor unless clearly separated.
- Large rewrites.
- New patterns inconsistent with the codebase.
