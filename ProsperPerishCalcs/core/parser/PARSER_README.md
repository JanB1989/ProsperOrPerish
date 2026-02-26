# Core Parsing Engine

Robust Paradox script parser with support for nested blocks and mod overrides.

## Components

- `base_parser.py`: Abstract base for file reading and comment stripping.
- `paradox_parser.py`: Recursive brace-matching parser handling `INJECT` and `REPLACE`.
- `path_resolver.py`: Resolves mirrored vanilla and mod directory structures.
- `exceptions.py`: Explicit error types for parsing and file operations.
- `syntax_rules.md`: Documentation of Paradox script logic.

## Parsing Logic

The parser is designed to handle the unique "cascading" nature of Paradox scripts:
1. **Brace Matching**: Handles deeply nested blocks (e.g., `pop_demand = { ... }`).
2. **Mod Prefixes**: Supports `INJECT`, `REPLACE`, `TRY_INJECT`, and `TRY_REPLACE` for non-destructive and destructive modding.
3. **Key-Value Pairs**: Correctly identifies keys and values, including those with special characters like `@` and `.`.
4. **List Support**: Automatically converts repeated keys into lists of values.
