#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import uuid as uuid_module
import time
import shutil
import subprocess
from pathlib import Path

def get_remarkable_path():
    """Get platform-specific reMarkable desktop app path"""
    if os.name == 'nt':  # Windows
        app_data = os.getenv('APPDATA')
        return Path(app_data) / 'remarkable' / 'desktop'
    elif os.uname().sysname == 'Darwin':  # macOS
        return Path.home() / 'Library/Containers/com.remarkable.desktop/Data/Library/Application Support/remarkable/desktop'
    else:  # Linux
        return Path.home() / '.local/share/remarkable/desktop'


def check_remarkable_app_installed():
    """
    Check if the reMarkable desktop app is installed and accessible.

    Returns:
        tuple: (is_installed, path_or_message)
    """
    rm_path = get_remarkable_path()
    if rm_path.exists():
        return (True, str(rm_path))
    else:
        return (False, f"reMarkable desktop app not found at:\n{rm_path}\n\n"
                       "Please install the reMarkable desktop app and log in to your account.")


def is_remarkable_app_running():
    """Check if the reMarkable desktop app is currently running."""
    try:
        if os.name == 'nt':  # Windows
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq reMarkable.exe'],
                capture_output=True, text=True, timeout=5
            )
            return 'reMarkable.exe' in result.stdout
        else:  # macOS and Linux
            result = subprocess.run(
                ['pgrep', '-f', 'reMarkable'],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
    except Exception:
        return False


def stop_remarkable_app():
    """
    Stop the reMarkable desktop app.

    Returns:
        bool: True if stopped successfully or wasn't running
    """
    try:
        if os.name == 'nt':  # Windows
            subprocess.run(
                ['taskkill', '/F', '/IM', 'reMarkable.exe'],
                capture_output=True, timeout=10
            )
        else:  # macOS and Linux
            subprocess.run(
                ['pkill', '-f', 'reMarkable'],
                capture_output=True, timeout=10
            )
        # Wait a moment for the app to fully close
        time.sleep(1)
        return True
    except Exception:
        return False


def start_remarkable_app():
    """
    Start the reMarkable desktop app.

    Returns:
        bool: True if started successfully
    """
    try:
        if os.name == 'nt':  # Windows
            app_path = Path(os.getenv('APPDATA')) / 'remarkable' / 'reMarkable.exe'
            if app_path.exists():
                subprocess.Popen([str(app_path)], start_new_session=True)
                return True
        elif os.uname().sysname == 'Darwin':  # macOS
            subprocess.Popen(
                ['open', '-a', 'reMarkable'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return True
        else:  # Linux
            subprocess.Popen(
                ['remarkable'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            return True
    except Exception:
        pass
    return False

def get_all_folders():
    """Get all (non-trashed) folders from reMarkable, with full paths.

    Each entry has ``uuid``, ``name`` (leaf), ``path`` (slash-joined
    visibleName chain from the top, e.g. "Books / Fiction"), and
    ``pinned``. Trashed folders are excluded. Orphaned folders (parent
    UUID points to something that's gone) appear at the top level.
    """
    rm_path = get_remarkable_path()

    if not rm_path.exists():
        return []

    by_uuid = {}
    for metadata_file in rm_path.glob('*.metadata'):
        try:
            with open(metadata_file) as f:
                metadata = json.load(f)
        except Exception:
            continue
        if metadata.get('type') != 'CollectionType':
            continue
        if metadata.get('parent', '') == 'trash':
            continue
        uuid = metadata_file.stem
        by_uuid[uuid] = {
            'uuid': uuid,
            'name': metadata.get('visibleName', 'Unknown'),
            'parent': metadata.get('parent', ''),
            'pinned': metadata.get('pinned', False),
        }

    def build_path(uuid):
        parts = []
        seen = set()
        current = uuid
        while current and current in by_uuid and current not in seen:
            seen.add(current)
            node = by_uuid[current]
            parts.append(node['name'])
            current = node['parent']
        return list(reversed(parts))

    folders = []
    for uuid, node in by_uuid.items():
        path_parts = build_path(uuid)
        folders.append({
            'uuid': uuid,
            'name': node['name'],
            'path': ' / '.join(path_parts),
            'pinned': node['pinned'],
        })

    folders.sort(key=lambda x: x['path'].lower())
    return folders


def get_pdf_page_count(pdf_path):
    """Get the number of pages in a PDF file"""
    import subprocess

    # Method 1: Try pdfinfo (from poppler-utils)
    try:
        result = subprocess.run(['pdfinfo', pdf_path],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.startswith('Pages:'):
                    return int(line.split(':')[1].strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass

    # Method 2: Try PyPDF2 (if available)
    try:
        import PyPDF2
        with open(pdf_path, 'rb') as f:
            pdf = PyPDF2.PdfReader(f)
            return len(pdf.pages)
    except (ImportError, Exception):
        pass

    # Method 3: Try pikepdf (if available)
    try:
        import pikepdf
        with pikepdf.open(pdf_path) as pdf:
            return len(pdf.pages)
    except (ImportError, Exception):
        pass

    # Method 4: Try Calibre's PDF reader
    try:
        from calibre.ebooks.pdf.render.from_html import PDFStream
        from io import BytesIO

        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()

        stream = PDFStream(BytesIO(pdf_data), False)
        return stream.page_count()
    except Exception:
        pass

    # Method 5: Count PDF page objects directly
    try:
        with open(pdf_path, 'rb') as f:
            content = f.read()
            # Look for /Type /Page entries
            import re
            pages = re.findall(rb'/Type\s*/Page[^s]', content)
            if pages:
                return len(pages)
    except Exception:
        pass

    # Method 6: Use qpdf if available
    try:
        result = subprocess.run(['qpdf', '--show-npages', pdf_path],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return int(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass

    # If all methods fail, estimate from file size (rough approximation)
    # Average PDF page is ~50-100KB, use conservative estimate
    try:
        file_size = os.path.getsize(pdf_path)
        estimated_pages = max(1, file_size // 75000)  # Conservative estimate
        return estimated_pages
    except Exception:
        pass

    # Last resort: return a default value
    return 100  # Default page count if all else fails

def find_existing_document(title, folder_uuid=''):
    """
    Find an existing document by title in the reMarkable directory.

    Args:
        title: Document title to search for
        folder_uuid: Optional folder to search in (empty string for root)

    Returns:
        dict with 'uuid', 'title', 'parent' or None if not found
    """
    rm_path = get_remarkable_path()

    if not rm_path.exists():
        return None

    for metadata_file in rm_path.glob('*.metadata'):
        try:
            with open(metadata_file) as f:
                metadata = json.load(f)

            if (metadata.get('type') == 'DocumentType' and
                metadata.get('visibleName') == title and
                metadata.get('parent', '') == folder_uuid):

                return {
                    'uuid': metadata_file.stem,
                    'title': metadata.get('visibleName'),
                    'parent': metadata.get('parent', '')
                }
        except Exception:
            continue

    return None


def update_existing_document(pdf_path, doc_uuid):
    """
    Update an existing document's PDF file only.
    Preserves metadata, annotations, and reading position.

    Args:
        pdf_path: Path to new PDF file
        doc_uuid: UUID of existing document

    Returns:
        tuple: (success, message)
    """
    rm_path = get_remarkable_path()

    if not rm_path.exists():
        return (False, "reMarkable directory not found")

    try:
        # Get new page count
        new_page_count = get_pdf_page_count(pdf_path)
        new_file_size = os.path.getsize(pdf_path)

        # Update PDF file
        shutil.copy(pdf_path, rm_path / f"{doc_uuid}.pdf")

        # Update .content with new page count and size
        content_path = rm_path / f"{doc_uuid}.content"
        if content_path.exists():
            with open(content_path) as f:
                content = json.load(f)

            old_page_count = content.get('pageCount', 0)

            # If page count changed, generate new page UUIDs for additional pages
            if new_page_count > old_page_count:
                existing_pages = content.get('pages', [])
                for _ in range(new_page_count - old_page_count):
                    existing_pages.append(str(uuid_module.uuid4()))
                content['pages'] = existing_pages
            elif new_page_count < old_page_count:
                content['pages'] = content.get('pages', [])[:new_page_count]

            content['pageCount'] = new_page_count
            content['originalPageCount'] = new_page_count
            content['sizeInBytes'] = str(new_file_size)

            with open(content_path, 'w') as f:
                json.dump(content, f, indent=4)

        # Update .metadata lastModified timestamp
        metadata_path = rm_path / f"{doc_uuid}.metadata"
        if metadata_path.exists():
            with open(metadata_path) as f:
                metadata = json.load(f)

            metadata['lastModified'] = str(int(time.time() * 1000))

            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=4)

        # Update .pagedata if page count changed
        pagedata_path = rm_path / f"{doc_uuid}.pagedata"
        if pagedata_path.exists():
            with open(pagedata_path, 'w') as f:
                f.write('\n' * (new_page_count + 1))

        return (True, "Document updated successfully")

    except Exception as e:
        return (False, f"Error updating document: {str(e)}")


def send_to_remarkable(pdf_path, title, folder_uuid='', author=None):
    """
    Send PDF to reMarkable desktop app

    Returns:
        tuple: (success, uuid, message)
    """
    rm_path = get_remarkable_path()
    
    if not rm_path.exists():
        return (False, None, f"reMarkable desktop app directory not found at {rm_path}")
    
    # Get page count
    page_count = get_pdf_page_count(pdf_path)
    if page_count is None:
        return (False, None, "Could not determine PDF page count")
    
    # Get file size
    file_size = os.path.getsize(pdf_path)
    
    # Generate UUIDs
    doc_uuid = str(uuid_module.uuid4())
    page_uuids = [str(uuid_module.uuid4()) for _ in range(page_count)]
    
    try:
        # 1. Copy PDF
        shutil.copy(pdf_path, rm_path / f"{doc_uuid}.pdf")
        
        # 2. Create .metadata
        timestamp_ms = str(int(time.time() * 1000))
        metadata = {
            "createdTime": timestamp_ms,
            "lastModified": timestamp_ms,
            "lastOpened": timestamp_ms,
            "lastOpenedPage": 0,
            "new": True,
            "parent": folder_uuid,
            "pinned": False,
            "source": "",
            "type": "DocumentType",
            "visibleName": title
        }
        
        with open(rm_path / f"{doc_uuid}.metadata", 'w') as f:
            json.dump(metadata, f, indent=4)
        
        # 3. Create .content
        content = {
            "coverPageNumber": 0,
            "customZoomCenterX": 0,
            "customZoomCenterY": 936,
            "customZoomOrientation": "portrait",
            "customZoomPageHeight": 1872,
            "customZoomPageWidth": 1404,
            "customZoomScale": 1,
            "documentMetadata": {
                "authors": [author] if author else [],
                "title": title
            },
            "extraMetadata": {},
            "fileType": "pdf",
            "fontName": "",
            "formatVersion": 1,
            "lineHeight": -1,
            "margins": 125,
            "orientation": "portrait",
            "originalPageCount": page_count,
            "pageCount": page_count,
            "pageTags": [],
            "pages": page_uuids,
            "sizeInBytes": str(file_size),
            "tags": [],
            "textAlignment": "justify",
            "textScale": 1,
            "zoomMode": "bestFit"
        }
        
        with open(rm_path / f"{doc_uuid}.content", 'w') as f:
            json.dump(content, f, indent=4)
        
        # 4. Create .local
        local = {"contentFormatVersion": 1}
        with open(rm_path / f"{doc_uuid}.local", 'w') as f:
            json.dump(local, f, indent=4)
        
        # 5. Create .pagedata (empty lines)
        with open(rm_path / f"{doc_uuid}.pagedata", 'w') as f:
            f.write('\n' * (page_count + 1))
        
        # 6. Create annotation directory
        (rm_path / doc_uuid).mkdir(exist_ok=True)
        
        # 7. Create thumbnails directory
        (rm_path / f"{doc_uuid}.thumbnails").mkdir(exist_ok=True)
        
        return (True, doc_uuid, f"Successfully sent '{title}' to reMarkable")
        
    except Exception as e:
        return (False, None, f"Error: {str(e)}")

def get_reading_position(doc_uuid):
    """Get reading position for a document"""
    rm_path = get_remarkable_path()
    metadata_path = rm_path / f"{doc_uuid}.metadata"

    if not metadata_path.exists():
        return None

    try:
        with open(metadata_path) as f:
            metadata = json.load(f)

        return {
            'page': metadata.get('lastOpenedPage', 0),
            'last_opened': metadata.get('lastOpened', '0')
        }
    except:
        return None


def get_all_documents_with_progress(folder_uuid=None):
    """
    Get documents from reMarkable with their reading progress.

    Args:
        folder_uuid: If provided, only return documents in this folder.
                     Empty string means root folder.

    Returns:
        list of dicts with 'uuid', 'title', 'page', 'total_pages', 'progress', 'last_read'
    """
    rm_path = get_remarkable_path()

    if not rm_path.exists():
        return []

    documents = []

    for metadata_file in rm_path.glob('*.metadata'):
        try:
            with open(metadata_file) as f:
                metadata = json.load(f)

            # Only process documents (not folders)
            if metadata.get('type') != 'DocumentType':
                continue

            # Filter by folder if specified
            if folder_uuid is not None:
                doc_parent = metadata.get('parent', '')
                if doc_parent != folder_uuid:
                    continue

            doc_uuid = metadata_file.stem
            title = metadata.get('visibleName', '')
            current_page = metadata.get('lastOpenedPage', 0) + 1  # Convert from 0-indexed to 1-indexed
            last_opened_ms = metadata.get('lastOpened', '0')

            # Get total pages from .content file
            content_path = rm_path / f"{doc_uuid}.content"
            total_pages = 0
            if content_path.exists():
                try:
                    with open(content_path) as f:
                        content = json.load(f)
                    total_pages = content.get('pageCount', 0)
                except:
                    pass

            # Calculate progress as 0-100 percentage (compatible with Reading Goal)
            progress = 0.0
            if total_pages > 0:
                progress = round((current_page / total_pages) * 100, 1)

            # Convert timestamp (milliseconds since epoch, reMarkable uses UTC)
            last_read = None
            if last_opened_ms and last_opened_ms != '0':
                try:
                    from datetime import datetime, timezone
                    last_read = datetime.fromtimestamp(int(last_opened_ms) / 1000, tz=timezone.utc)
                except:
                    pass

            documents.append({
                'uuid': doc_uuid,
                'title': title,
                'page': current_page,
                'total_pages': total_pages,
                'progress': progress,
                'last_read': last_read,
            })

        except Exception:
            continue

    return documents
