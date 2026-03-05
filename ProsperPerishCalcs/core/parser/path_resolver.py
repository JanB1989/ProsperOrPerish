import os

class PathResolver:
    """Handles mirroring between vanilla and mod paths in EUV."""

    def __init__(self, game_path, mod_path):
        self.game_path = game_path
        self.mod_path = mod_path

    def resolve_path(self, relative_path):
        """
        Returns a list of absolute paths for a given relative path.
        Always includes the vanilla path and the mod path if it exists.
        """
        paths = []
        
        # Vanilla path
        vanilla_path = os.path.join(self.game_path, relative_path)
        if os.path.exists(vanilla_path):
            paths.append(vanilla_path)
        
        # Mod path (mirrored structure)
        mod_path = os.path.join(self.mod_path, relative_path)
        if os.path.exists(mod_path):
            paths.append(mod_path)
            
        return paths

    def get_mod_files(self, relative_dir):
        """Returns all files in a mod directory that mirror a vanilla directory."""
        mod_dir = os.path.join(self.mod_path, relative_dir)
        if not os.path.exists(mod_dir):
            return []
        
        return [os.path.join(mod_dir, f) for f in os.listdir(mod_dir) if f.endswith('.txt')]

    def get_vanilla_files(self, relative_dir):
        """Returns all files in a vanilla directory."""
        vanilla_dir = os.path.join(self.game_path, relative_dir)
        if not os.path.exists(vanilla_dir):
            return []
        
        return [os.path.join(vanilla_dir, f) for f in os.listdir(vanilla_dir) if f.endswith('.txt')]
