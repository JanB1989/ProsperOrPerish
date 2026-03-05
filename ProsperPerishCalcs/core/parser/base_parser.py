import os
from abc import ABC, abstractmethod
from .exceptions import MissingFileError, ParadoxParseError

class BaseParser(ABC):
    """Abstract base class for all Paradox file parsers."""

    def __init__(self):
        pass

    def read_file(self, file_path):
        """Reads a file and returns its content, ensuring it exists."""
        if not os.path.exists(file_path):
            raise MissingFileError(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                return f.read()
        except Exception as e:
            raise ParadoxParseError(f"Failed to read file: {str(e)}", file_path=file_path)

    @abstractmethod
    def parse(self, file_path):
        """Main parsing method to be implemented by subclasses."""
        pass

    def strip_comments(self, content):
        """Removes Paradox-style comments (#) from the content."""
        lines = content.splitlines()
        stripped_lines = []
        for line in lines:
            if '#' in line:
                line = line.split('#')[0]
            stripped_lines.append(line)
        return "\n".join(stripped_lines)
