from dataclasses import dataclass
from pathlib import Path

@dataclass
class MediaFile:
    path: Path
    type: str #image or video
    metadata: dict = None

    def extract_metadata(self):
        """Extract metadata from the media file and populate the metadata attribute."""
        pass

    def generate_output_filename(self, filename_template: str):
        """Generate an output filename based on the given template and attributes available in metadata."""
        pass

    def move(self, destination: Path):
        """Move the media file to the specified destination and update self.path."""
        pass