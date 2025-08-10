from pathlib import Path
from typing import List, Dict, Set, Optional, Callable
import mimetypes
from collections import defaultdict
import concurrent.futures
from .media_file import MediaFile


class MediaHandler:
    """Class to handle file detection and folder scanning."""
    
    # Supported file extensions
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', 
                       '.webp', '.heic', '.heif', '.raw', '.cr2', '.nef', '.arw', 
                       '.dng', '.orf', '.rw2', '.pef', '.srw'}
    
    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', 
                       '.m4v', '.3gp', '.ogv', '.f4v', '.asf', '.rm', '.rmvb', 
                       '.vob', '.ts', '.mts', '.m2ts'}
    
    def __init__(self, base_directory: Optional[Path] = None):
        """
        Initialize MediaHandler.
        
        Args:
            base_directory: Base directory for scanning operations
        """
        self.base_directory = Path(base_directory) if base_directory else None
        self.media_files: List[MediaFile] = []
        self.scan_stats = {
            'total_files_found': 0,
            'images_found': 0,
            'videos_found': 0,
            'skipped_files': 0,
            'errors': 0,
            'duplicates_found': 0
        }
        self._file_hashes: Dict[str, MediaFile] = {}  # For duplicate detection
        
    def scan_directory(self, directory: Path, glob_pattern: str = '*', 
                      recursive: bool = True, max_workers: int = 4) -> None:
        """
        Scans a directory and populates the media_files list with MediaFile objects.
        
        Args:
            directory: Directory to scan
            glob_pattern: Glob pattern for file matching (default: '*')
            recursive: Whether to scan subdirectories recursively
            max_workers: Number of worker threads for parallel processing
        """
        directory = Path(directory)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        if not directory.is_dir():
            raise ValueError(f"Path is not a directory: {directory}")
        
        # Reset stats and file list
        self._reset_scan_stats()
        self.media_files.clear()
        self._file_hashes.clear()
        
        print(f"Scanning directory: {directory}")
        print(f"Pattern: {glob_pattern}, Recursive: {recursive}")
        
        # Find all files matching the pattern
        if recursive:
            files = list(directory.rglob(glob_pattern))
        else:
            files = list(directory.glob(glob_pattern))
        
        # Filter for media files only
        media_files = [f for f in files if f.is_file() and self._is_media_file(f)]
        self.scan_stats['total_files_found'] = len(media_files)
        
        if not media_files:
            print("No media files found.")
            return
        
        print(f"Found {len(media_files)} potential media files. Processing...")
        
        # Process files in parallel for better performance
        if max_workers > 1 and len(media_files) > 10:
            self._process_files_parallel(media_files, max_workers)
        else:
            self._process_files_sequential(media_files)
        
        # Sort files by path for consistent ordering
        self.media_files.sort(key=lambda x: str(x.path))
        
        self._print_scan_summary()
    
    def _process_files_sequential(self, files: List[Path]) -> None:
        """Process files sequentially."""
        for file_path in files:
            self._process_single_file(file_path)
    
    def _process_files_parallel(self, files: List[Path], max_workers: int) -> None:
        """Process files in parallel using ThreadPoolExecutor."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_file = {executor.submit(self._create_media_file, file_path): file_path 
                            for file_path in files}
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    media_file = future.result()
                    if media_file:
                        self._add_media_file(media_file)
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    self.scan_stats['errors'] += 1
    
    def _process_single_file(self, file_path: Path) -> None:
        """Process a single file and add it to the media_files list."""
        try:
            media_file = self._create_media_file(file_path)
            if media_file:
                self._add_media_file(media_file)
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            self.scan_stats['errors'] += 1
    
    def _create_media_file(self, file_path: Path) -> Optional[MediaFile]:
        """Create a MediaFile object from a file path."""
        try:
            file_type = self._detect_file_type(file_path)
            if file_type:
                return MediaFile(path=file_path, type=file_type)
            else:
                self.scan_stats['skipped_files'] += 1
                return None
        except Exception as e:
            print(f"Failed to create MediaFile for {file_path}: {e}")
            self.scan_stats['errors'] += 1
            return None
    
    def _add_media_file(self, media_file: MediaFile) -> None:
        """Add a media file to the collection, checking for duplicates."""
        # Extract metadata to get file hash
        media_file.extract_metadata()
        file_hash = media_file.metadata.get('file_hash')
        
        if file_hash and file_hash in self._file_hashes:
            # Duplicate found
            self.scan_stats['duplicates_found'] += 1
            print(f"Duplicate found: {media_file.path} (matches {self._file_hashes[file_hash].path})")
        else:
            # Add to collection
            self.media_files.append(media_file)
            if file_hash:
                self._file_hashes[file_hash] = media_file
            
            # Update stats
            if media_file.type == 'image':
                self.scan_stats['images_found'] += 1
            elif media_file.type == 'video':
                self.scan_stats['videos_found'] += 1
    
    def _is_media_file(self, file_path: Path) -> bool:
        """Check if a file is a supported media file."""
        extension = file_path.suffix.lower()
        return extension in self.IMAGE_EXTENSIONS or extension in self.VIDEO_EXTENSIONS
    
    def _detect_file_type(self, file_path: Path) -> Optional[str]:
        """Detect if file is image or video based on extension and MIME type."""
        extension = file_path.suffix.lower()
        
        # Check by extension first (faster)
        if extension in self.IMAGE_EXTENSIONS:
            return 'image'
        elif extension in self.VIDEO_EXTENSIONS:
            return 'video'
        
        # Fallback to MIME type detection
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type:
            if mime_type.startswith('image/'):
                return 'image'
            elif mime_type.startswith('video/'):
                return 'video'
        
        return None
    
    def _reset_scan_stats(self) -> None:
        """Reset scan statistics."""
        self.scan_stats = {
            'total_files_found': 0,
            'images_found': 0,
            'videos_found': 0,
            'skipped_files': 0,
            'errors': 0,
            'duplicates_found': 0
        }
    
    def _print_scan_summary(self) -> None:
        """Print a summary of the scan results."""
        stats = self.scan_stats
        print("\n" + "="*50)
        print("SCAN SUMMARY")
        print("="*50)
        print(f"Total files processed: {stats['total_files_found']}")
        print(f"Images found: {stats['images_found']}")
        print(f"Videos found: {stats['videos_found']}")
        print(f"Duplicates found: {stats['duplicates_found']}")
        print(f"Files skipped: {stats['skipped_files']}")
        print(f"Errors: {stats['errors']}")
        print(f"Successfully processed: {len(self.media_files)}")
        print("="*50)
    
    def filter_by_type(self, file_type: str) -> List[MediaFile]:
        """
        Filter media files by type.
        
        Args:
            file_type: 'image' or 'video'
            
        Returns:
            List of MediaFile objects of the specified type
        """
        return [mf for mf in self.media_files if mf.type == file_type]
    
    def filter_by_extension(self, extensions: Set[str]) -> List[MediaFile]:
        """
        Filter media files by file extensions.
        
        Args:
            extensions: Set of extensions (e.g., {'.jpg', '.png'})
            
        Returns:
            List of MediaFile objects with matching extensions
        """
        extensions = {ext.lower() for ext in extensions}
        return [mf for mf in self.media_files if mf.path.suffix.lower() in extensions]
    
    def filter_by_size(self, min_size_mb: float = 0, max_size_mb: float = float('inf')) -> List[MediaFile]:
        """
        Filter media files by file size.
        
        Args:
            min_size_mb: Minimum file size in MB
            max_size_mb: Maximum file size in MB
            
        Returns:
            List of MediaFile objects within the size range
        """
        filtered = []
        for mf in self.media_files:
            if not mf.metadata:
                mf.extract_metadata()
            size_mb = mf.metadata.get('file_size_mb', 0)
            if min_size_mb <= size_mb <= max_size_mb:
                filtered.append(mf)
        return filtered
    
    def find_duplicates(self) -> Dict[str, List[MediaFile]]:
        """
        Find duplicate files based on file hash.
        
        Returns:
            Dictionary mapping file hashes to lists of duplicate MediaFile objects
        """
        hash_groups = defaultdict(list)
        
        for media_file in self.media_files:
            if not media_file.metadata:
                media_file.extract_metadata()
            
            file_hash = media_file.metadata.get('file_hash')
            if file_hash:
                hash_groups[file_hash].append(media_file)
        
        # Return only groups with more than one file (duplicates)
        return {hash_val: files for hash_val, files in hash_groups.items() if len(files) > 1}
    
    def get_files_by_date_range(self, start_date=None, end_date=None, 
                               date_field: str = 'date_taken') -> List[MediaFile]:
        """
        Filter files by date range.
        
        Args:
            start_date: Start date (datetime object)
            end_date: End date (datetime object)
            date_field: Metadata field to use for date filtering
            
        Returns:
            List of MediaFile objects within the date range
        """
        filtered = []
        for mf in self.media_files:
            if not mf.metadata:
                mf.extract_metadata()
            
            file_date = mf.metadata.get(date_field)
            if file_date:
                if start_date and file_date < start_date:
                    continue
                if end_date and file_date > end_date:
                    continue
                filtered.append(mf)
        
        return filtered
    
    def organize_files(self, output_directory: Path, filename_template: str, 
                      folder_structure: str = "{year}/{month}", 
                      operation: str = 'copy', dry_run: bool = False) -> Dict[str, int]:
        """
        Organize files into a structured directory layout.
        
        Args:
            output_directory: Base output directory
            filename_template: Template for generating filenames
            folder_structure: Template for folder structure (e.g., "{year}/{month}")
            operation: 'copy' or 'move'
            dry_run: If True, only simulate the operation
            
        Returns:
            Dictionary with operation statistics
        """
        output_directory = Path(output_directory)
        stats = {'processed': 0, 'errors': 0, 'skipped': 0}
        
        print(f"\n{'DRY RUN: ' if dry_run else ''}Organizing {len(self.media_files)} files...")
        print(f"Output directory: {output_directory}")
        print(f"Filename template: {filename_template}")
        print(f"Folder structure: {folder_structure}")
        print(f"Operation: {operation}")
        
        for media_file in self.media_files:
            try:
                # Generate new filename
                new_filename = media_file.generate_output_filename(filename_template)
                
                # Generate folder structure
                if not media_file.metadata:
                    media_file.extract_metadata()
                
                # Create template variables for folder structure
                folder_vars = self._get_folder_template_vars(media_file)
                folder_path = folder_structure.format(**folder_vars)
                
                # Full destination path
                destination = output_directory / folder_path / new_filename
                
                print(f"{'[DRY RUN] ' if dry_run else ''}{media_file.path} -> {destination}")
                
                if not dry_run:
                    if operation == 'move':
                        media_file.move(destination)
                    elif operation == 'copy':
                        media_file.copy(destination)
                    else:
                        raise ValueError(f"Invalid operation: {operation}")
                
                stats['processed'] += 1
                
            except Exception as e:
                print(f"Error organizing {media_file.path}: {e}")
                stats['errors'] += 1
        
        print(f"\nOrganization {'simulation ' if dry_run else ''}complete!")
        print(f"Processed: {stats['processed']}, Errors: {stats['errors']}")
        
        return stats
    
    def _get_folder_template_vars(self, media_file: MediaFile) -> Dict[str, str]:
        """Get template variables for folder structure generation."""
        vars_dict = {
            'type': media_file.type,
            'year': '',
            'month': '',
            'day': '',
            'camera_make': '',
            'camera_model': '',
        }
        
        # Extract date information
        date_source = None
        if media_file.type == 'image' and 'date_taken' in media_file.metadata:
            date_source = media_file.metadata['date_taken']
        elif media_file.type == 'video' and 'date_created' in media_file.metadata:
            date_source = media_file.metadata['date_created']
        elif 'created_date' in media_file.metadata:
            date_source = media_file.metadata['created_date']
        
        if date_source:
            vars_dict.update({
                'year': str(date_source.year),
                'month': f"{date_source.month:02d}",
                'day': f"{date_source.day:02d}",
            })
        
        # Add camera info for images
        if media_file.type == 'image':
            vars_dict['camera_make'] = media_file.metadata.get('camera_make', 'Unknown')
            vars_dict['camera_model'] = media_file.metadata.get('camera_model', 'Unknown')
        
        return vars_dict
    
    def get_summary_stats(self) -> Dict[str, any]:
        """Get comprehensive statistics about the media collection."""
        if not self.media_files:
            return {'message': 'No media files loaded'}
        
        # Basic counts
        images = self.filter_by_type('image')
        videos = self.filter_by_type('video')
        
        # Size statistics
        total_size = sum(mf.metadata.get('file_size_mb', 0) for mf in self.media_files 
                        if mf.metadata)
        
        # Extension distribution
        extensions = defaultdict(int)
        for mf in self.media_files:
            extensions[mf.path.suffix.lower()] += 1
        
        return {
            'total_files': len(self.media_files),
            'images': len(images),
            'videos': len(videos),
            'total_size_mb': round(total_size, 2),
            'total_size_gb': round(total_size / 1024, 2),
            'extensions': dict(extensions),
            'duplicates': len(self.find_duplicates()),
            'scan_stats': self.scan_stats.copy()
        }
    
    def clear(self) -> None:
        """Clear all loaded media files and reset statistics."""
        self.media_files.clear()
        self._file_hashes.clear()
        self._reset_scan_stats()
        print("MediaHandler cleared.")
    
    def __len__(self) -> int:
        """Return the number of media files."""
        return len(self.media_files)
    
    def __iter__(self):
        """Make MediaHandler iterable."""
        return iter(self.media_files)
    
    def __getitem__(self, index):
        """Allow indexing into media files."""
        return self.media_files[index]