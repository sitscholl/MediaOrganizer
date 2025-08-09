
from pathlib import Path
from .media_file import MediaFile

class MediaHandler:
    """Class to handle file detection and folder scanning."""
    def __init__(self, directory: Path):
        self.media_files = []
        pass

    def scan_directory(self, directory: Path, glob: str = '*', recursive: bool = False) -> None:
        """Scans a directory and populates the media_files list with objects of type MediaFile."""
        pass