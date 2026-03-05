# Paradox Script Syntax Rules

This document outlines the syntax rules used by the `ParadoxParser` and how mod overrides are handled.

## Basic Syntax
- Key-value pairs: `key = value`
- Nested blocks: `key = { ... }`
- Comments: Start with `#` and continue to the end of the line.
- Strings: Can be quoted `"value"` or unquoted.

## Mod Overrides (TRY_INJECT and TRY_REPLACE)
EUV uses specific prefixes to handle how mod data interacts with vanilla data.

### TRY_INJECT
- **Syntax**: `TRY_INJECT:entity_name = { ... }`
- **Behavior**: **Merging/Additive**. 
- The parser identifies these blocks and the data modules merge the contained properties into the existing definition of `entity_name`.
- If a property already exists, it is overwritten or added depending on the specific game logic.

### TRY_REPLACE
- **Syntax**: `TRY_REPLACE:entity_name = { ... }`
- **Behavior**: **Full Replacement**.
- The parser identifies these blocks and the data modules completely replace any existing definition of `entity_name` with the content of this block.

### TRY_INJECT vs TRY_REPLACE in Files
- These prefixes are often used in mod files that mirror the path of vanilla files.
- The `PathResolver` and `DataModules` use these rules to construct the final "active" game state.

## Error Handling
- **Silent errors are forbidden**.
- Unmatched braces must raise a `ParadoxParseError`.
- Missing required files must raise a `MissingFileError`.
- Syntax violations must raise a `SyntaxRuleError`.
