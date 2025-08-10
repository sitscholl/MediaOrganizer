from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any
import shutil
import hashlib
from datetime import datetime
import mimetypes

# For metadata extraction
try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

try:
    import ffmpeg
    FFMPEG_AVAILABLE = True
except ImportError:
    FFMPEG_AVAILABLE = False

@dataclass
class MediaFile:
    path: Path
    type: str  # image or video
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)
    manual_metadata: Optional[Dict[str, Any]] = field(default_factory=dict)  # New field for manual metadata
    
    def __post_init__(self):
        """Initialize after dataclass creation."""
        if not self.path.exists():
            raise FileNotFoundError(f"File not found: {self.path}")
        
        # Auto-detect type if not provided or validate provided type
        detected_type = self._detect_file_type()
        if self.type not in ['image', 'video']:
            self.type = detected_type
        elif self.type != detected_type:
            raise ValueError(f"Provided type '{self.type}' doesn't match detected type '{detected_type}'")

    def _detect_file_type(self) -> str:
        """Detect if file is image or video based on MIME type."""
        mime_type, _ = mimetypes.guess_type(str(self.path))
        if mime_type:
            if mime_type.startswith('image/'):
                return 'image'
            elif mime_type.startswith('video/'):
                return 'video'
        
        # Fallback to extension-based detection
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.heic', '.raw'}
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.3gp'}
        
        ext = self.path.suffix.lower()
        if ext in image_extensions:
            return 'image'
        elif ext in video_extensions:
            return 'video'
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    def set_manual_metadata(self, key: str, value: Any) -> None:
        """Set manual metadata for the file."""
        if self.manual_metadata is None:
            self.manual_metadata = {}
        self.manual_metadata[key] = value

    def get_manual_metadata(self, key: str, default: Any = None) -> Any:
        """Get manual metadata value."""
        if self.manual_metadata is None:
            return default
        return self.manual_metadata.get(key, default)

    def update_manual_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Update multiple manual metadata fields at once."""
        if self.manual_metadata is None:
            self.manual_metadata = {}
        self.manual_metadata.update(metadata_dict)

    def get_combined_metadata(self) -> Dict[str, Any]:
        """Get combined metadata (extracted + manual), with manual taking precedence."""
        combined = self.metadata.copy() if self.metadata else {}
        if self.manual_metadata:
            combined.update(self.manual_metadata)
        return combined

    def extract_metadata(self):
        """Extract metadata from the media file and populate the metadata attribute."""
        try:
            # Common metadata for all files
            stat = self.path.stat()
            self.metadata.update({
                'filename': self.path.name,
                'file_size': stat.st_size,
                'file_size_mb': round(stat.st_size / (1024 * 1024), 2),
                'created_date': datetime.fromtimestamp(stat.st_ctime),
                'modified_date': datetime.fromtimestamp(stat.st_mtime),
                'file_extension': self.path.suffix.lower(),
                'file_hash': self._calculate_file_hash(),
            })
            
            if self.type == 'image':
                self._extract_image_metadata()
            elif self.type == 'video':
                self._extract_video_metadata()
                
        except Exception as e:
            print(f"Error extracting metadata from {self.path}: {e}")
            # Ensure we have at least basic metadata
            if not self.metadata:
                self.metadata = {'filename': self.path.name, 'error': str(e)}

    def _extract_image_metadata(self):
        """Extract EXIF and other metadata from image files."""
        if not PILLOW_AVAILABLE:
            print("PIL/Pillow not available. Install with: pip install Pillow")
            return
            
        try:
            with Image.open(self.path) as img:
                # Basic image info
                self.metadata.update({
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode,
                    'resolution': f"{img.width}x{img.height}"
                })
                
                # EXIF data
                exif_data = img._getexif()
                if exif_data:
                    exif = {}
                    for tag_id, value in exif_data.items():
                        tag = TAGS.get(tag_id, tag_id)
                        exif[tag] = value
                    
                    # Extract commonly used EXIF data
                    if 'DateTime' in exif:
                        try:
                            self.metadata['date_taken'] = datetime.strptime(exif['DateTime'], '%Y:%m:%d %H:%M:%S')
                        except ValueError:
                            pass
                    
                    if 'Make' in exif:
                        self.metadata['camera_make'] = exif['Make']
                    if 'Model' in exif:
                        self.metadata['camera_model'] = exif['Model']
                    if 'GPS' in exif or any('GPS' in str(k) for k in exif.keys()):
                        self.metadata['has_gps'] = True
                    
                    # Store full EXIF data
                    self.metadata['exif'] = exif
                    
        except Exception as e:
            print(f"Error extracting image metadata: {e}")

    def _extract_video_metadata(self):
        """Extract metadata from video files using ffmpeg."""
        if not FFMPEG_AVAILABLE:
            print("ffmpeg-python not available. Install with: pip install ffmpeg-python")
            return
            
        try:
            probe = ffmpeg.probe(str(self.path))
            
            # General format info
            format_info = probe.get('format', {})
            self.metadata.update({
                'duration': float(format_info.get('duration', 0)),
                'duration_formatted': self._format_duration(float(format_info.get('duration', 0))),
                'bit_rate': int(format_info.get('bit_rate', 0)),
                'format_name': format_info.get('format_name', ''),
            })
            
            # Video stream info
            video_streams = [s for s in probe['streams'] if s['codec_type'] == 'video']
            if video_streams:
                video = video_streams[0]
                self.metadata.update({
                    'width': int(video.get('width', 0)),
                    'height': int(video.get('height', 0)),
                    'resolution': f"{video.get('width', 0)}x{video.get('height', 0)}",
                    'codec': video.get('codec_name', ''),
                    'fps': eval(video.get('r_frame_rate', '0/1')),  # Convert fraction to float
                })
            
            # Audio stream info
            audio_streams = [s for s in probe['streams'] if s['codec_type'] == 'audio']
            if audio_streams:
                audio = audio_streams[0]
                self.metadata.update({
                    'audio_codec': audio.get('codec_name', ''),
                    'sample_rate': int(audio.get('sample_rate', 0)),
                    'channels': int(audio.get('channels', 0)),
                })
            
            # Creation date from metadata
            if 'tags' in format_info:
                tags = format_info['tags']
                for date_key in ['creation_time', 'date', 'DATE']:
                    if date_key in tags:
                        try:
                            self.metadata['date_created'] = datetime.fromisoformat(tags[date_key].replace('Z', '+00:00'))
                            break
                        except ValueError:
                            continue
                            
        except Exception as e:
            print(f"Error extracting video metadata: {e}")

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to HH:MM:SS format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _calculate_file_hash(self, algorithm: str = 'md5') -> str:
        """Calculate file hash for duplicate detection."""
        hash_func = hashlib.new(algorithm)
        with open(self.path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()

    def generate_output_filename(self, filename_template: str) -> str:
        """Generate an output filename based on the given template and metadata."""
        # Use combined metadata (extracted + manual)
        combined_metadata = self.get_combined_metadata()
        
        # Available template variables
        template_vars = {
            'original_name': self.path.stem,
            'extension': self.path.suffix,
            'type': self.type,
            'year': '',
            'month': '',
            'day': '',
            'hour': '',
            'minute': '',
            'second': '',
            'width': '',
            'height': '',
            'resolution': '',
            'camera_make': '',
            'camera_model': '',
            'file_hash': combined_metadata.get('file_hash', '')[:8],  # First 8 chars of hash
        }
        
        # Add manual metadata fields to template variables
        if self.manual_metadata:
            for key, value in self.manual_metadata.items():
                template_vars[f'manual_{key}'] = str(value) if value is not None else ''
        
        # Extract date information (prefer date_taken for images, date_created for videos)
        date_source = None
        if self.type == 'image' and 'date_taken' in combined_metadata:
            date_source = combined_metadata['date_taken']
        elif self.type == 'video' and 'date_created' in combined_metadata:
            date_source = combined_metadata['date_created']
        elif 'created_date' in combined_metadata:
            date_source = combined_metadata['created_date']
        
        if date_source:
            template_vars.update({
                'year': str(date_source.year),
                'month': f"{date_source.month:02d}",
                'day': f"{date_source.day:02d}",
                'hour': f"{date_source.hour:02d}",
                'minute': f"{date_source.minute:02d}",
                'second': f"{date_source.second:02d}",
            })
        
        # Add dimension info
        if 'width' in combined_metadata:
            template_vars['width'] = str(combined_metadata['width'])
        if 'height' in combined_metadata:
            template_vars['height'] = str(combined_metadata['height'])
        if 'resolution' in combined_metadata:
            template_vars['resolution'] = combined_metadata['resolution']
        
        # Add camera info for images
        if self.type == 'image':
            template_vars['camera_make'] = combined_metadata.get('camera_make', '')
            template_vars['camera_model'] = combined_metadata.get('camera_model', '')
        
        # Replace template variables
        try:
            filename = filename_template.format(**template_vars)
            # Clean up any double spaces or invalid characters
            filename = ''.join(c for c in filename if c.isalnum() or c in '._-() ')
            filename = ' '.join(filename.split())  # Remove multiple spaces
            return filename
        except KeyError as e:
            raise ValueError(f"Template variable {e} not available in metadata")

    def move(self, destination: Path):
        """Move the media file to the specified destination and update self.path."""
        destination = Path(destination)
        
        # Create destination directory if it doesn't exist
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        # Handle filename conflicts
        if destination.exists():
            counter = 1
            stem = destination.stem
            suffix = destination.suffix
            while destination.exists():
                new_name = f"{stem}_{counter}{suffix}"
                destination = destination.parent / new_name
                counter += 1
        
        try:
            # Move the file
            shutil.move(str(self.path), str(destination))
            # Update the path
            old_path = self.path
            self.path = destination
            print(f"Moved {old_path} -> {destination}")
        except Exception as e:
            raise RuntimeError(f"Failed to move file: {e}")

    def copy(self, destination: Path):
        """Copy the media file to the specified destination without changing self.path."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        # Handle filename conflicts
        if destination.exists():
            counter = 1
            stem = destination.stem
            suffix = destination.suffix
            while destination.exists():
                new_name = f"{stem}_{counter}{suffix}"
                destination = destination.parent / new_name
                counter += 1
        
        try:
            shutil.copy2(str(self.path), str(destination))
            print(f"Copied {self.path} -> {destination}")
            return destination
        except Exception as e:
            raise RuntimeError(f"Failed to copy file: {e}")

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the media file information."""
        combined_metadata = self.get_combined_metadata()
        
        summary = {
            'path': str(self.path),
            'type': self.type,
            'filename': combined_metadata.get('filename', ''),
            'size_mb': combined_metadata.get('file_size_mb', 0),
        }
        
        if self.type == 'image':
            summary.update({
                'resolution': combined_metadata.get('resolution', ''),
                'format': combined_metadata.get('format', ''),
                'date_taken': combined_metadata.get('date_taken', ''),
                'camera': f"{combined_metadata.get('camera_make', '')} {combined_metadata.get('camera_model', '')}".strip(),
            })
        elif self.type == 'video':
            summary.update({
                'resolution': combined_metadata.get('resolution', ''),
                'duration': combined_metadata.get('duration_formatted', ''),
                'codec': combined_metadata.get('codec', ''),
                'fps': combined_metadata.get('fps', 0),
            })
        
        # Add manual metadata to summary
        if self.manual_metadata:
            summary['manual_metadata'] = self.manual_metadata.copy()
        
        return summary

    def is_duplicate(self, other: 'MediaFile') -> bool:
        """Check if this file is a duplicate of another MediaFile based on hash."""
        combined_self = self.get_combined_metadata()
        combined_other = other.get_combined_metadata()
        
        return (combined_self.get('file_hash') == combined_other.get('file_hash') and 
                combined_self.get('file_hash') is not None)

    def __str__(self) -> str:
        return f"MediaFile({self.path.name}, {self.type})"

    def __repr__(self) -> str:
        return f"MediaFile(path='{self.path}', type='{self.type}')"