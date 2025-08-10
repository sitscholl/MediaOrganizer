import streamlit as st
import os
from pathlib import Path
import pandas as pd
from datetime import datetime, date
import json
from typing import Dict, List, Any

# Import our custom classes
from src.handler import MediaHandler
from src.media_file import MediaFile

# Configure Streamlit page
st.set_page_config(
    page_title="Media Organizer",
    page_icon="📁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'handler' not in st.session_state:
    st.session_state.handler = MediaHandler()
if 'scanned_files' not in st.session_state:
    st.session_state.scanned_files = []
if 'selected_files' not in st.session_state:
    st.session_state.selected_files = []
if 'manual_metadata_cache' not in st.session_state:
    st.session_state.manual_metadata_cache = {}

def get_available_drives():
    """Get available drives on the system."""
    drives = []
    if os.name == 'nt':  # Windows
        import string
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append(drive)
    else:  # Unix-like systems
        drives = ['/']
        # Add common mount points
        common_mounts = ['/media', '/mnt', '/Volumes']
        for mount in common_mounts:
            if os.path.exists(mount):
                try:
                    for item in os.listdir(mount):
                        mount_path = os.path.join(mount, item)
                        if os.path.isdir(mount_path):
                            drives.append(mount_path)
                except PermissionError:
                    pass
    return drives

def browse_directory(start_path: str = None):
    """Create a directory browser interface."""
    if start_path is None:
        start_path = os.getcwd()
    
    current_path = Path(start_path)
    
    # Show current path
    st.write(f"📂 Current path: `{current_path}`")
    
    # Parent directory button
    if current_path.parent != current_path:
        if st.button("⬆️ Parent Directory"):
            return str(current_path.parent)
    
    # List directories
    try:
        directories = [d for d in current_path.iterdir() if d.is_dir()]
        directories.sort()
        
        if directories:
            cols = st.columns(3)
            for i, directory in enumerate(directories):
                with cols[i % 3]:
                    if st.button(f"📁 {directory.name}", key=f"dir_{i}"):
                        return str(directory)
        else:
            st.info("No subdirectories found.")
    except PermissionError:
        st.error("Permission denied to access this directory.")
    except Exception as e:
        st.error(f"Error accessing directory: {e}")
    
    return str(current_path)

def display_file_details(media_file: MediaFile, index: int):
    """Display detailed information about a media file."""
    with st.expander(f"📄 {media_file.path.name}", expanded=False):
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.write("**File Information:**")
            summary = media_file.get_summary()
            st.write(f"- **Type:** {summary['type'].title()}")
            st.write(f"- **Size:** {summary['size_mb']} MB")
            st.write(f"- **Path:** `{summary['path']}`")
            
            if media_file.type == 'image':
                st.write(f"- **Resolution:** {summary.get('resolution', 'N/A')}")
                st.write(f"- **Format:** {summary.get('format', 'N/A')}")
                if summary.get('camera'):
                    st.write(f"- **Camera:** {summary['camera']}")
                if summary.get('date_taken'):
                    st.write(f"- **Date Taken:** {summary['date_taken']}")
            elif media_file.type == 'video':
                st.write(f"- **Resolution:** {summary.get('resolution', 'N/A')}")
                st.write(f"- **Duration:** {summary.get('duration', 'N/A')}")
                st.write(f"- **Codec:** {summary.get('codec', 'N/A')}")
                st.write(f"- **FPS:** {summary.get('fps', 'N/A')}")
        
        with col2:
            st.write("**Manual Metadata:**")
            
            # Get current manual metadata
            current_manual = media_file.manual_metadata or {}
            
            # Common manual metadata fields
            manual_fields = {
                'title': st.text_input(f"Title", value=current_manual.get('title', ''), key=f"title_{index}"),
                'description': st.text_area(f"Description", value=current_manual.get('description', ''), key=f"desc_{index}"),
                'tags': st.text_input(f"Tags (comma-separated)", value=current_manual.get('tags', ''), key=f"tags_{index}"),
                'location': st.text_input(f"Location", value=current_manual.get('location', ''), key=f"location_{index}"),
                'event': st.text_input(f"Event", value=current_manual.get('event', ''), key=f"event_{index}"),
                'people': st.text_input(f"People", value=current_manual.get('people', ''), key=f"people_{index}"),
                'rating': st.selectbox(f"Rating", options=[None, 1, 2, 3, 4, 5], 
                                     index=0 if current_manual.get('rating') is None else current_manual.get('rating'), 
                                     key=f"rating_{index}"),
                'custom_date': st.date_input(f"Custom Date", 
                                           value=current_manual.get('custom_date', date.today()), 
                                           key=f"custom_date_{index}")
            }
            
            # Update manual metadata
            updated_metadata = {}
            for key, value in manual_fields.items():
                if value:  # Only add non-empty values
                    if key == 'custom_date':
                        updated_metadata[key] = datetime.combine(value, datetime.min.time())
                    else:
                        updated_metadata[key] = value
            
            if updated_metadata != current_manual:
                media_file.update_manual_metadata(updated_metadata)
                st.session_state.manual_metadata_cache[str(media_file.path)] = updated_metadata

def create_filename_template_builder():
    """Create an interactive filename template builder."""
    st.subheader("🏗️ Filename Template Builder")
    
    # Available template variables
    template_vars = {
        'Basic': ['original_name', 'extension', 'type', 'file_hash'],
        'Date/Time': ['year', 'month', 'day', 'hour', 'minute', 'second'],
        'Media Info': ['width', 'height', 'resolution', 'camera_make', 'camera_model'],
        'Manual Metadata': ['manual_title', 'manual_event', 'manual_location', 'manual_tags', 'manual_people', 'manual_rating']
    }
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.write("**Available Variables:**")
        for category, vars_list in template_vars.items():
            with st.expander(f"{category} Variables"):
                for var in vars_list:
                    st.code(f"{{{var}}}")
    
    with col2:
        st.write("**Template Builder:**")
        
        # Predefined templates
        predefined_templates = {
            "Original": "{original_name}{extension}",
            "Date + Original": "{year}-{month}-{day}_{original_name}{extension}",
            "Date + Resolution": "{year}-{month}-{day}_{resolution}_{original_name}{extension}",
            "Event + Date": "{manual_event}_{year}-{month}-{day}_{original_name}{extension}",
            "Location + Date": "{manual_location}_{year}-{month}-{day}_{original_name}{extension}",
            "Custom": ""
        }
        
        template_choice = st.selectbox("Choose a template:", list(predefined_templates.keys()))
        
        if template_choice == "Custom":
            filename_template = st.text_input("Custom template:", value="{year}-{month}-{day}_{original_name}{extension}")
        else:
            filename_template = predefined_templates[template_choice]
            st.code(filename_template)
    
    return filename_template

def create_folder_structure_builder():
    """Create an interactive folder structure builder."""
    st.subheader("📁 Folder Structure Builder")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Predefined folder structures
        predefined_structures = {
            "Flat (no folders)": "",
            "By Year": "{year}",
            "By Year/Month": "{year}/{month}",
            "By Type": "{type}",
            "By Type/Year": "{type}/{year}",
            "By Event": "{manual_event}",
            "By Location": "{manual_location}",
            "By Camera": "{camera_make}/{camera_model}",
            "Custom": ""
        }
        
        structure_choice = st.selectbox("Choose folder structure:", list(predefined_structures.keys()))
        
        if structure_choice == "Custom":
            folder_structure = st.text_input("Custom folder structure:", value="{year}/{month}")
        else:
            folder_structure = predefined_structures[structure_choice]
            if folder_structure:
                st.code(folder_structure)
    
    with col2:
        st.write("**Example folder structures:**")
        st.code("Photos/2024/01/")
        st.code("Videos/2024/")
        st.code("Events/Birthday/")
        st.code("Locations/Paris/")
    
    return folder_structure

# Main App
st.title("📁 Media Organizer")
st.markdown("Organize your images and videos with metadata extraction and custom naming schemes.")

# Sidebar for navigation
with st.sidebar:
    st.header("Navigation")
    page = st.radio("Choose a section:", [
        "📂 1. Select Directory",
        "🔍 2. Scan & Review Files", 
        "✏️ 3. Edit Metadata",
        "⚙️ 4. Configure Organization",
        "🚀 5. Execute Organization"
    ])

# Page 1: Directory Selection
if page == "📂 1. Select Directory":
    st.header("📂 Select Input Directory")
    
    # Method selection
    selection_method = st.radio("How would you like to select the directory?", [
        "Browse directories",
        "Enter path manually"
    ])
    
    selected_directory = None
    
    if selection_method == "Browse directories":
        st.subheader("Directory Browser")
        
        # Initialize current path
        if 'current_browse_path' not in st.session_state:
            st.session_state.current_browse_path = os.getcwd()
        
        # Drive/root selection
        drives = get_available_drives()
        if len(drives) > 1:
            selected_drive = st.selectbox("Select drive/root:", drives)
            if st.button("Go to selected drive"):
                st.session_state.current_browse_path = selected_drive
                st.rerun()
        
        # Directory browser
        new_path = browse_directory(st.session_state.current_browse_path)
        if new_path != st.session_state.current_browse_path:
            st.session_state.current_browse_path = new_path
            st.rerun()
        
        # Select current directory button
        if st.button("✅ Select Current Directory"):
            selected_directory = st.session_state.current_browse_path
    
    else:  # Manual path entry
        manual_path = st.text_input("Enter directory path:", value=os.getcwd())
        if st.button("Validate Path"):
            if os.path.exists(manual_path) and os.path.isdir(manual_path):
                selected_directory = manual_path
                st.success(f"✅ Valid directory: {manual_path}")
            else:
                st.error("❌ Invalid directory path")
    
    # Store selected directory
    if selected_directory:
        st.session_state.selected_directory = selected_directory
        st.success(f"📂 Selected directory: `{selected_directory}`")
        
        # Show directory info
        try:
            path_obj = Path(selected_directory)
            files = list(path_obj.iterdir())
            total_files = len([f for f in files if f.is_file()])
            total_dirs = len([f for f in files if f.is_dir()])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Files", total_files)
            with col2:
                st.metric("Subdirectories", total_dirs)
            with col3:
                # Estimate media files
                media_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.avi', '.mov', '.mkv'}
                media_files = len([f for f in files if f.is_file() and f.suffix.lower() in media_extensions])
                st.metric("Potential Media Files", media_files)
        except Exception as e:
            st.warning(f"Could not analyze directory: {e}")

# Page 2: Scan & Review Files
elif page == "🔍 2. Scan & Review Files":
    st.header("🔍 Scan & Review Files")
    
    if 'selected_directory' not in st.session_state:
        st.warning("⚠️ Please select a directory first.")
        st.stop()
    
    # Scanning options
    col1, col2, col3 = st.columns(3)
    with col1:
        glob_pattern = st.text_input("File pattern:", value="*", help="Use * for all files, *.jpg for specific extensions")
    with col2:
        recursive = st.checkbox("Scan subdirectories", value=True)
    with col3:
        max_workers = st.slider("Parallel workers:", 1, 8, 4)
    
    # Scan button
    if st.button("🔍 Start Scanning", type="primary"):
        with st.spinner("Scanning directory..."):
            try:
                st.session_state.handler.scan_directory(
                    Path(st.session_state.selected_directory),
                    glob_pattern=glob_pattern,
                    recursive=recursive,
                    max_workers=max_workers
                )
                st.session_state.scanned_files = st.session_state.handler.media_files
                st.success(f"✅ Scan complete! Found {len(st.session_state.scanned_files)} media files.")
            except Exception as e:
                st.error(f"❌ Scan failed: {e}")
    
    # Display scan results
    if st.session_state.scanned_files:
        stats = st.session_state.handler.get_summary_stats()
        
        # Statistics
        st.subheader("📊 Scan Statistics")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Files", stats['total_files'])
        with col2:
            st.metric("Images", stats['images'])
        with col3:
            st.metric("Videos", stats['videos'])
        with col4:
            st.metric("Total Size", f"{stats['total_size_gb']:.2f} GB")
        
        # File type distribution
        if stats['extensions']:
            st.subheader("📈 File Type Distribution")
            ext_df = pd.DataFrame(list(stats['extensions'].items()), columns=['Extension', 'Count'])
            st.bar_chart(ext_df.set_index('Extension'))
        
        # Files list with filters
        st.subheader("📋 Found Files")
        
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            type_filter = st.selectbox("Filter by type:", ["All", "Images", "Videos"])
        with col2:
            min_size = st.number_input("Min size (MB):", min_value=0.0, value=0.0)
        with col3:
            max_size = st.number_input("Max size (MB):", min_value=0.0, value=1000.0)
        
        # Apply filters
        filtered_files = st.session_state.scanned_files
        if type_filter == "Images":
            filtered_files = [f for f in filtered_files if f.type == 'image']
        elif type_filter == "Videos":
            filtered_files = [f for f in filtered_files if f.type == 'video']
        
        if min_size > 0 or max_size < 1000:
            filtered_files = [f for f in filtered_files 
                            if min_size <= f.metadata.get('file_size_mb', 0) <= max_size]
        
        st.write(f"Showing {len(filtered_files)} of {len(st.session_state.scanned_files)} files")
        
        # Display files in a table
        if filtered_files:
            file_data = []
            for i, media_file in enumerate(filtered_files):
                summary = media_file.get_summary()
                file_data.append({
                    'Select': False,
                    'Filename': summary['filename'],
                    'Type': summary['type'].title(),
                    'Size (MB)': summary['size_mb'],
                    'Resolution': summary.get('resolution', 'N/A'),
                    'Path': str(media_file.path.parent)
                })
            
            df = pd.DataFrame(file_data)
            edited_df = st.data_editor(df, use_container_width=True, key="file_selection")
            
            # Store selected files
            selected_indices = [i for i, row in edited_df.iterrows() if row['Select']]
            st.session_state.selected_files = [filtered_files[i] for i in selected_indices]
            
            if st.session_state.selected_files:
                st.success(f"✅ Selected {len(st.session_state.selected_files)} files for processing.")

# Page 3: Edit Metadata
elif page == "✏️ 3. Edit Metadata":
    st.header("✏️ Edit Metadata")
    
    if not st.session_state.selected_files:
        st.warning("⚠️ Please scan and select files first.")
        st.stop()
    
    st.write(f"Editing metadata for {len(st.session_state.selected_files)} selected files.")
    
    # Bulk metadata editing
    st.subheader("🔄 Bulk Edit Metadata")
    with st.expander("Apply to all selected files"):
        bulk_metadata = {}
        
        col1, col2 = st.columns(2)
        with col1:
            bulk_event = st.text_input("Event (bulk):", key="bulk_event")
            bulk_location = st.text_input("Location (bulk):", key="bulk_location")
            bulk_tags = st.text_input("Tags (bulk):", key="bulk_tags")
        with col2:
            bulk_people = st.text_input("People (bulk):", key="bulk_people")
            bulk_rating = st.selectbox("Rating (bulk):", [None, 1, 2, 3, 4, 5], key="bulk_rating")
            bulk_date = st.date_input("Custom Date (bulk):", key="bulk_date")
        
        if st.button("Apply Bulk Metadata"):
            bulk_updates = {}
            if bulk_event: bulk_updates['event'] = bulk_event
            if bulk_location: bulk_updates['location'] = bulk_location
            if bulk_tags: bulk_updates['tags'] = bulk_tags
            if bulk_people: bulk_updates['people'] = bulk_people
            if bulk_rating: bulk_updates['rating'] = bulk_rating
            if bulk_date: bulk_updates['custom_date'] = datetime.combine(bulk_date, datetime.min.time())
            
            if bulk_updates:
                for media_file in st.session_state.selected_files:
                    media_file.update_manual_metadata(bulk_updates)
                st.success(f"✅ Applied bulk metadata to {len(st.session_state.selected_files)} files.")
                st.rerun()
    
    # Individual file editing
    st.subheader("📝 Individual File Editing")
    
    # Pagination for large numbers of files
    files_per_page = 5
    total_pages = (len(st.session_state.selected_files) - 1) // files_per_page + 1
    
    if total_pages > 1:
        page_num = st.selectbox("Page:", range(1, total_pages + 1)) - 1
    else:
        page_num = 0
    
    start_idx = page_num * files_per_page
    end_idx = min(start_idx + files_per_page, len(st.session_state.selected_files))
    
    for i in range(start_idx, end_idx):
        display_file_details(st.session_state.selected_files[i], i)

# Page 4: Configure Organization
elif page == "⚙️ 4. Configure Organization":
    st.header("⚙️ Configure Organization")
    
    if not st.session_state.selected_files:
        st.warning("⚠️ Please scan and select files first.")
        st.stop()
    
    # Output directory selection
    st.subheader("📂 Output Directory")
    output_method = st.radio("Select output directory:", ["Browse", "Enter manually"])
    
    if output_method == "Browse":
        if 'output_browse_path' not in st.session_state:
            st.session_state.output_browse_path = os.getcwd()
        
        new_output_path = browse_directory(st.session_state.output_browse_path)
        if new_output_path != st.session_state.output_browse_path:
            st.session_state.output_browse_path = new_output_path
            st.rerun()
        
        if st.button("✅ Select as Output Directory"):
            st.session_state.output_directory = st.session_state.output_browse_path
    else:
        manual_output = st.text_input("Output directory path:", value=os.path.join(os.getcwd(), "organized"))
        if st.button("Set Output Directory"):
            st.session_state.output_directory = manual_output
    
    if 'output_directory' in st.session_state:
        st.success(f"📂 Output directory: `{st.session_state.output_directory}`")
    
    # Template configuration
    filename_template = create_filename_template_builder()
    folder_structure = create_folder_structure_builder()
    
    # Operation type
    st.subheader("🔧 Operation Settings")
    col1, col2 = st.columns(2)
    with col1:
        operation = st.radio("Operation type:", ["Copy files", "Move files"])
    with col2:
        dry_run = st.checkbox("Dry run (preview only)", value=True)
    
    # Preview
    if st.button("🔍 Preview Organization"):
        if 'output_directory' not in st.session_state:
            st.error("❌ Please select an output directory first.")
        else:
            st.subheader("📋 Organization Preview")
            
            preview_data = []
            for media_file in st.session_state.selected_files[:10]:  # Limit preview to 10 files
                try:
                    new_filename = media_file.generate_output_filename(filename_template)
                    
                    # Generate folder path
                    combined_metadata = media_file.get_combined_metadata()
                    folder_vars = {
                        'type': media_file.type,
                        'year': '',
                        'month': '',
                        'day': '',
                        'camera_make': combined_metadata.get('camera_make', 'Unknown'),
                        'camera_model': combined_metadata.get('camera_model', 'Unknown'),
                    }
                    
                    # Add manual metadata to folder vars
                    if media_file.manual_metadata:
                        for key, value in media_file.manual_metadata.items():
                            folder_vars[f'manual_{key}'] = str(value) if value else 'Unknown'
                    
                    # Extract date for folder structure
                    date_source = None
                    if media_file.type == 'image' and 'date_taken' in combined_metadata:
                        date_source = combined_metadata['date_taken']
                    elif media_file.type == 'video' and 'date_created' in combined_metadata:
                        date_source = combined_metadata['date_created']
                    elif 'created_date' in combined_metadata:
                        date_source = combined_metadata['created_date']
                    
                    if date_source:
                        folder_vars.update({
                            'year': str(date_source.year),
                            'month': f"{date_source.month:02d}",
                            'day': f"{date_source.day:02d}",
                        })
                    
                    if folder_structure:
                        folder_path = folder_structure.format(**folder_vars)
                        full_path = Path(st.session_state.output_directory) / folder_path / new_filename
                    else:
                        full_path = Path(st.session_state.output_directory) / new_filename
                    
                    preview_data.append({
                        'Original': media_file.path.name,
                        'New Path': str(full_path),
                        'Operation': operation.split()[0].title()
                    })
                    
                except Exception as e:
                    preview_data.append({
                        'Original': media_file.path.name,
                        'New Path': f"ERROR: {e}",
                        'Operation': "Failed"
                    })
            
            if len(st.session_state.selected_files) > 10:
                st.info(f"Showing preview for first 10 files. Total files to process: {len(st.session_state.selected_files)}")
            
            preview_df = pd.DataFrame(preview_data)
            st.dataframe(preview_df, use_container_width=True)
    
    # Store configuration
    st.session_state.filename_template = filename_template
    st.session_state.folder_structure = folder_structure
    st.session_state.operation_type = operation
    st.session_state.dry_run = dry_run

# Page 5: Execute Organization
elif page == "🚀 5. Execute Organization":
    st.header("🚀 Execute Organization")
    
    # Check prerequisites
    missing_requirements = []
    if not st.session_state.selected_files:
        missing_requirements.append("Select files to organize")
    if 'output_directory' not in st.session_state:
        missing_requirements.append("Select output directory")
    if 'filename_template' not in st.session_state:
        missing_requirements.append("Configure filename template")
    
    if missing_requirements:
        st.error("❌ Missing requirements:")
        for req in missing_requirements:
            st.write(f"- {req}")
        st.stop()
    
    # Show configuration summary
    st.subheader("📋 Configuration Summary")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Files:**")
        st.write(f"- Selected files: {len(st.session_state.selected_files)}")
        st.write(f"- Images: {len([f for f in st.session_state.selected_files if f.type == 'image'])}")
        st.write(f"- Videos: {len([f for f in st.session_state.selected_files if f.type == 'video'])}")
        
        st.write("**Templates:**")
        st.code(st.session_state.filename_template)
        if st.session_state.folder_structure:
            st.code(st.session_state.folder_structure)
    
    with col2:
        st.write("**Settings:**")
        st.write(f"- Output directory: `{st.session_state.output_directory}`")
        st.write(f"- Operation: {st.session_state.operation_type}")
        st.write(f"- Dry run: {'Yes' if st.session_state.dry_run else 'No'}")
        
        # Calculate total size
        total_size = sum(f.metadata.get('file_size_mb', 0) for f in st.session_state.selected_files)
        st.write(f"- Total size: {total_size:.2f} MB ({total_size/1024:.2f} GB)")
    
    # Execute button
    execute_button_text = "🔍 Run Dry Run" if st.session_state.dry_run else "🚀 Execute Organization"
    execute_button_type = "secondary" if st.session_state.dry_run else "primary"
    
    if st.button(execute_button_text, type=execute_button_type):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Use the MediaHandler's organize_files method
            operation_type = 'copy' if 'Copy' in st.session_state.operation_type else 'move'
            
            stats = st.session_state.handler.organize_files(
                output_directory=Path(st.session_state.output_directory),
                filename_template=st.session_state.filename_template,
                folder_structure=st.session_state.folder_structure,
                operation=operation_type,
                dry_run=st.session_state.dry_run
            )
            
            progress_bar.progress(1.0)
            status_text.success("✅ Organization complete!")
            
            # Show results
            st.subheader("📊 Results")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Processed", stats['processed'])
            with col2:
                st.metric("Errors", stats['errors'])
            with col3:
                st.metric("Success Rate", f"{(stats['processed']/(stats['processed']+stats['errors'])*100):.1f}%")
            
            if not st.session_state.dry_run:
                st.success("🎉 Files have been successfully organized!")
                st.balloons()
            else:
                st.info("ℹ️ This was a dry run. No files were actually moved or copied.")
                
        except Exception as e:
            st.error(f"❌ Organization failed: {e}")
            progress_bar.progress(0)

# Footer
st.markdown("---")
st.markdown("📁 **Media Organizer** - Organize your photos and videos with ease!")