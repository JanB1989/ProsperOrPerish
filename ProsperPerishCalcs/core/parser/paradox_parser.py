import re
from .base_parser import BaseParser
from .exceptions import ParadoxParseError

class ParadoxParser(BaseParser):
    """Robust parser for Paradox .txt files handling nested structures and TRY blocks."""

    def __init__(self):
        super().__init__()

    def parse(self, file_path):
        """Parses a Paradox file into a nested dictionary structure."""
        content = self.read_file(file_path)
        content = self.strip_comments(content)
        return self._parse_content(content, file_path)

    def _parse_content(self, content, file_path):
        """Internal recursive parser using brace matching."""
        results = {}
        
        # Pattern to match key = value or key = { ... }
        # Also handles INJECT:key, REPLACE:key, TRY_INJECT:key and TRY_REPLACE:key
        # Updated to handle more characters in keys like @ and .
        pattern = re.compile(r'((?:TRY_INJECT|TRY_REPLACE|INJECT|REPLACE):)?([\w.:@]+)\s*=\s*({|"(?:[^"\\]|\\.)*"|[^\s{}#]+)', re.IGNORECASE)
        
        pos = 0
        while pos < len(content):
            match = pattern.search(content, pos)
            if not match:
                # Check if the remaining content is a list of values (no keys)
                remaining = content[pos:].strip()
                if remaining and not any(c in remaining for c in ['=', '{', '}']):
                    values = remaining.split()
                    return [self._convert_value(v) for v in values]
                break
            
            prefix, key, value_start = match.groups()
            full_key = (prefix if prefix else "") + key
            
            start_idx = match.end()
            
            if value_start == '{':
                # Nested block
                depth = 1
                end_idx = start_idx
                while depth > 0 and end_idx < len(content):
                    if content[end_idx] == '{':
                        depth += 1
                    elif content[end_idx] == '}':
                        depth -= 1
                    end_idx += 1
                
                if depth > 0:
                    line_no = content.count('\n', 0, match.start()) + 1
                    raise ParadoxParseError(f"Unmatched opening brace for key '{full_key}'", file_path, line_no)
                
                block_content = content[start_idx:end_idx-1]
                block_data = self._parse_content(block_content, file_path)
                
                self._add_to_results(results, full_key, block_data)
                pos = end_idx
            else:
                # Simple value
                val = self._convert_value(value_start.strip('"'))
                self._add_to_results(results, full_key, val)
                pos = start_idx
                
        # If we found no key-value pairs but the content isn't empty, 
        # it might be a simple list of values without braces
        if not results and content.strip():
            values = content.strip().split()
            if values and not any('=' in v for v in values):
                return [self._convert_value(v) for v in values]

        return results

    def _convert_value(self, val):
        """Tries to convert a string value to a numeric type."""
        try:
            if '.' in val or (val.isdigit() or (val.startswith('-') and val[1:].isdigit())):
                return float(val)
        except ValueError:
            pass
        return val

    def _add_to_results(self, results, key, value):
        """Handles duplicate keys by converting them to a list."""
        if key in results:
            if isinstance(results[key], list):
                results[key].append(value)
            else:
                results[key] = [results[key], value]
        else:
            results[key] = value
