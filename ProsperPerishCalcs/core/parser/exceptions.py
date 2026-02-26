class ParadoxError(Exception):
    """Base class for exceptions in this module."""
    pass

class ParadoxParseError(ParadoxError):
    """Exception raised for errors during parsing of Paradox files."""
    def __init__(self, message, file_path=None, line_number=None):
        self.file_path = file_path
        self.line_number = line_number
        full_message = f"Parse error in {file_path or 'unknown file'}"
        if line_number:
            full_message += f" at line {line_number}"
        full_message += f": {message}"
        super().__init__(full_message)

class MissingFileError(ParadoxError):
    """Exception raised when a required file is missing."""
    def __init__(self, file_path):
        super().__init__(f"Required file not found: {file_path}")

class SyntaxRuleError(ParadoxError):
    """Exception raised when a syntax rule is violated."""
    pass
