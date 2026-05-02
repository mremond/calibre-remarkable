#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Worker module for running EPUB->PDF conversion and sending to reMarkable.

Conversion runs via fork_job() in a separate process to avoid Qt event loop
conflicts. The outer function runs in a ThreadedJob for progress reporting.
"""

import os
import shutil
import tempfile


def convert_epub_to_pdf(epub_path, title, device_type='rmpp', font_family='', font_size=12.0,
                        line_height=125, margin_left=15, margin_right=15, margin_top=45,
                        margin_bottom=35, footer_template=''):
    """
    Convert EPUB to PDF using Calibre's Plumber.

    This function runs in a separate worker process via fork_job(),
    so it doesn't conflict with the GUI's Qt event loop.

    Args:
        epub_path: Path to the EPUB file
        title: Book title (used for output filename)
        device_type: reMarkable device type ('rm2', 'rmpp', 'rmpp_move')
        font_family: Font family name to embed (empty for default)
        font_size: PDF font size in pixels
        line_height: Line height as percentage (e.g., 125 for 125%)
        margin_left: Left margin in points
        margin_right: Right margin in points
        margin_top: Top margin in points
        margin_bottom: Bottom margin in points
        footer_template: HTML template for page footer

    Returns:
        dict with 'success', 'pdf_path', and 'error' keys
    """
    from calibre.customize.conversion import OptionRecommendation
    from calibre.ebooks.conversion.plumber import Plumber
    from calibre.utils.logging import Log
    from calibre_plugins.remarkable_sync.config import get_device_page_size

    # Create temp directory for output
    output_dir = tempfile.mkdtemp(prefix='remarkable_sync_')
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
    pdf_path = os.path.join(output_dir, f"{safe_title}.pdf")

    # Get device-specific page size in pixels
    page_width, page_height = get_device_page_size(device_type)
    custom_size = f'{page_width}x{page_height}'

    try:
        log = Log()
        plumber = Plumber(epub_path, pdf_path, log)

        HIGH = OptionRecommendation.HIGH

        extra_css = f'''
html, body {{
  margin: 0;
  orphans: 2;
  widows: 2;
  line-height: {line_height}%;
}}
html body p, html body div, html body li, html body td, html body th, html body blockquote,
p[class], div[class], li[class] {{
  font-size: 1em !important;
  font-family: inherit !important;
}}
html body h1, html body h2, html body h3, html body h4, html body h5, html body h6,
h1[class], h2[class], h3[class], h4[class], h5[class], h6[class],
.footnote, .footnote *, .note, .note *, .endnote, .endnote *,
sup, sub, small,
.dropcap, .initial, .drop-cap,
[class*="dropcap" i], [class*="Dropcap"], [class*="DropCap"] {{
  font-size: revert !important;
  font-family: revert !important;
}}
blockquote, .quote, .epigraph, .pullquote {{
  margin-left: 1.5em;
  margin-right: 1.5em;
  font-style: italic;
}}
'''

        recommendations = [
            ('pdf_page_numbers', False, HIGH),
            ('custom_size', custom_size, HIGH),
            ('unit', 'devicepixel', HIGH),
            ('output_profile', 'generic_eink_hd', HIGH),  # E-Ink generic HD profile
            ('smarten_punctuation', True, HIGH),
            ('extra_css', extra_css, HIGH),
            ('pdf_no_cover', True, HIGH),  # We add full-bleed cover separately
            ('pdf_hyphenate', True, HIGH),
            ('base_font_size', 12.0, HIGH),
            ('pdf_default_font_size', int(font_size), HIGH),
            ('pdf_mono_font_size', int(font_size * 0.77), HIGH),
            ('pdf_page_margin_left', margin_left, HIGH),
            ('pdf_page_margin_right', margin_right, HIGH),
            ('pdf_page_margin_top', margin_top, HIGH),
            ('pdf_page_margin_bottom', margin_bottom, HIGH),
            ('margin_left', margin_left, HIGH),
            ('margin_right', margin_right, HIGH),
            ('margin_top', margin_top, HIGH),
            ('margin_bottom', margin_bottom, HIGH),
        ]

        if font_family:
            recommendations.append(('embed_font_family', font_family, HIGH))
            recommendations.append(('pdf_serif_family', font_family, HIGH))
            recommendations.append(('embed_all_fonts', True, HIGH))

        if footer_template:
            recommendations.append(('pdf_footer_template', footer_template, HIGH))

        plumber.merge_ui_recommendations(recommendations)
        plumber.run()

        if os.path.exists(pdf_path):
            # Post-process: add full-bleed cover
            make_cover_fullbleed(epub_path, pdf_path, log)
            return {'success': True, 'pdf_path': pdf_path, 'error': ''}
        else:
            return {'success': False, 'pdf_path': None,
                    'error': 'Conversion completed but output file not created'}

    except Exception as e:
        import traceback
        return {'success': False, 'pdf_path': None, 'error': traceback.format_exc()}


def _rasterize_svg_cover(svg_data, target_width):
    """Rasterize SVG bytes to PNG bytes at *target_width* px wide.

    Returns PNG bytes on success, or None if the SVG cannot be parsed.
    """
    from calibre.gui2 import ensure_app
    from PyQt5.QtSvg import QSvgRenderer
    from PyQt5.QtGui import QImage, QPainter
    from PyQt5.QtCore import QByteArray, QBuffer, QIODevice

    ensure_app()

    renderer = QSvgRenderer(QByteArray(svg_data))
    if not renderer.isValid():
        return None

    default_size = renderer.defaultSize()
    if default_size.width() <= 0 or default_size.height() <= 0:
        return None

    aspect = default_size.height() / default_size.width()
    width = max(1, int(target_width))
    height = max(1, int(width * aspect))

    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(0xFFFFFFFF)
    painter = QPainter(image)
    try:
        renderer.render(painter)
    finally:
        painter.end()

    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    image.save(buf, 'PNG')
    return bytes(buf.data())


def _looks_like_svg(name, data):
    if name and name.lower().endswith('.svg'):
        return True
    head = data[:512].lstrip()
    if head.startswith(b'<svg'):
        return True
    return head.startswith(b'<?xml') and b'<svg' in data[:2048]


def make_cover_fullbleed(epub_path, pdf_path, log=None):
    """
    Add a full-bleed cover image as the first page of the PDF.

    Extracts the cover from the EPUB, resizes it to fit the page dimensions
    (top-aligned with padding at bottom if needed), and inserts it
    as the first page of the PDF.
    """
    if log is None:
        from calibre.utils.logging import default_log as log

    try:
        from calibre.ebooks.oeb.polish.container import get_container
        from calibre.ebooks.oeb.polish.cover import find_cover_image
        from calibre.utils.podofo import get_podofo
        from PIL import Image
        from io import BytesIO

        # Extract cover from EPUB
        container = get_container(epub_path)
        cover_name = find_cover_image(container)
        if not cover_name:
            log('reMarkable Sync: no cover image found in EPUB; skipping cover page')
            return

        cover_data = container.raw_data(cover_name)
        if not cover_data:
            log('reMarkable Sync: cover image %s is empty; skipping cover page' % cover_name)
            return

        # Load PDF to get page dimensions
        podofo = get_podofo()
        doc = podofo.PDFDoc()
        doc.open(pdf_path)

        if doc.page_count() < 1:
            return

        # Get first page dimensions (podofo uses 1-indexed page numbers)
        _, _, page_width, page_height = doc.get_page_box('MediaBox', 1)

        # PIL can't open SVG; rasterize via Qt at the page width for crisp output
        if _looks_like_svg(cover_name, cover_data):
            rasterized = _rasterize_svg_cover(cover_data, page_width)
            if rasterized is None:
                log('reMarkable Sync: failed to rasterize SVG cover %s; skipping cover page' % cover_name)
                return
            cover_data = rasterized

        # Pre-process image: resize to fit page width, add padding at bottom
        img = Image.open(BytesIO(cover_data))
        img_width, img_height = img.size

        # Scale to fit page width
        scale = page_width / img_width
        new_width = int(page_width)
        new_height = int(img_height * scale)

        img = img.resize((new_width, new_height), Image.LANCZOS)
        img_rgb = img.convert('RGB')

        # Get dominant color from bottom edge of image for padding
        bottom_row = [img_rgb.getpixel((x, new_height - 1)) for x in range(0, new_width, max(1, new_width // 20))]
        avg_r = sum(c[0] for c in bottom_row) // len(bottom_row)
        avg_g = sum(c[1] for c in bottom_row) // len(bottom_row)
        avg_b = sum(c[2] for c in bottom_row) // len(bottom_row)
        padding_color = (avg_r, avg_g, avg_b)

        # Create page-sized canvas with padding color, paste image at top
        canvas = Image.new('RGB', (int(page_width), int(page_height)), padding_color)
        canvas.paste(img_rgb, (0, 0))

        # Save as JPEG
        output = BytesIO()
        canvas.save(output, format='JPEG', quality=95)
        processed_cover_data = output.getvalue()

        # Add cover page at beginning
        doc.add_image_page(
            processed_cover_data,
            0.0, 0.0, page_width, page_height,
            0.0, 0.0, page_width, page_height,
            1, False
        )

        # Save to temp file then replace (podofo can't overwrite open file)
        temp_pdf = pdf_path + '.tmp'
        doc.save(temp_pdf)
        os.replace(temp_pdf, pdf_path)

    except Exception:
        # Keep the original PDF (without cover) but surface the cause
        import traceback
        log('reMarkable Sync: cover insertion failed:\n%s' % traceback.format_exc())


def check_existing_document(title, folder_uuid):
    """
    Check if a document with the same title exists.

    Args:
        title: Document title
        folder_uuid: Target folder UUID

    Returns:
        dict with document info or None
    """
    from calibre_plugins.remarkable_sync.remarkable import find_existing_document
    return find_existing_document(title, folder_uuid)


def process_single_book(book, folder_uuid, device_type, font_family, font_size, line_height,
                        margin_left, margin_right, margin_top, margin_bottom,
                        footer_template, auto_convert,
                        update_existing=False, existing_uuid=None):
    """
    Process a single book: convert if needed and send to reMarkable.

    Uses fork_job for EPUB conversion to run in separate process.
    Called from main thread with progress dialog.

    Args:
        book: Dict with 'book_id', 'title', 'author', 'format', 'path'
        folder_uuid: reMarkable folder UUID
        device_type: reMarkable device type for page sizing
        font_family: Font family name for conversion
        font_size: PDF font size for conversion
        line_height: Line height percentage for conversion
        margin_left: Left margin in points
        margin_right: Right margin in points
        margin_top: Top margin in points
        margin_bottom: Bottom margin in points
        footer_template: HTML template for page footer
        auto_convert: Whether to auto-convert EPUB to PDF
        update_existing: If True, update existing document instead of creating new
        existing_uuid: UUID of existing document to update

    Returns:
        tuple: (success, message, doc_uuid) - doc_uuid is None on failure or when updating
    """
    from calibre.utils.ipc.simple_worker import fork_job
    from calibre_plugins.remarkable_sync.remarkable import send_to_remarkable, update_existing_document

    title = book['title']
    author = book['author']
    fmt = book['format']
    path = book['path']

    pdf_path = None
    temp_dir = None

    try:
        if fmt == 'PDF':
            pdf_path = path
        elif fmt == 'EPUB':
            if not auto_convert:
                return (False, f'{title}: EPUB auto-conversion disabled', None)

            # Run conversion in separate process via fork_job
            result = fork_job(
                'calibre_plugins.remarkable_sync.worker',
                'convert_epub_to_pdf',
                args=(path, title, device_type, font_family, font_size, line_height,
                      margin_left, margin_right, margin_top, margin_bottom,
                      footer_template),
                timeout=600
            )

            if result.get('result'):
                data = result['result']
                if data['success']:
                    pdf_path = data['pdf_path']
                    temp_dir = os.path.dirname(pdf_path)
                else:
                    return (False, f'{title}: Conversion failed - {data.get("error", "Unknown error")}', None)
            else:
                return (False, f'{title}: Conversion worker failed', None)

        # Send to reMarkable (update or create new)
        if update_existing and existing_uuid:
            success, message = update_existing_document(pdf_path, existing_uuid)
            if success:
                return (True, f"Updated '{title}'", existing_uuid)
            else:
                return (False, f'{title}: {message}', None)
        else:
            success, doc_uuid, message = send_to_remarkable(
                pdf_path, title, folder_uuid, author
            )
            if success:
                return (True, message, doc_uuid)
            else:
                return (False, f'{title}: {message}', None)

    except Exception as e:
        return (False, f'{title}: {str(e)}', None)

    finally:
        # Clean up temp conversion files
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass


_FILENAME_FORBIDDEN = '<>:"/\\|?*'


def _sanitize_filename(name):
    cleaned = ''.join(c for c in name if c not in _FILENAME_FORBIDDEN).strip()
    return cleaned or 'book'


def _unique_pdf_path(directory, base):
    """Return a path under *directory* for *base*.pdf that does not yet exist.

    Avoids silently clobbering duplicate-titled exports or pre-existing files.
    """
    candidate = os.path.join(directory, f"{base}.pdf")
    if not os.path.exists(candidate):
        return candidate
    i = 2
    while True:
        candidate = os.path.join(directory, f"{base} ({i}).pdf")
        if not os.path.exists(candidate):
            return candidate
        i += 1


def export_single_book(book, output_dir, device_type, font_family, font_size, line_height,
                       margin_left, margin_right, margin_top, margin_bottom,
                       footer_template, auto_convert):
    """
    Export a single book as a reMarkable-tuned PDF into output_dir.

    PDF sources are copied as-is; EPUB sources are converted using the same
    pipeline as send_to_remarkable. Does not touch the reMarkable desktop
    app's storage.

    Returns:
        tuple: (success, message, output_path)
    """
    from calibre.utils.ipc.simple_worker import fork_job

    title = book['title']
    fmt = book['format']
    path = book['path']

    output_path = _unique_pdf_path(output_dir, _sanitize_filename(title))
    temp_dir = None

    try:
        if fmt == 'PDF':
            shutil.copy2(path, output_path)
            return (True, f"Exported '{title}'", output_path)

        if fmt == 'EPUB':
            if not auto_convert:
                return (False, f'{title}: EPUB auto-conversion disabled', None)

            result = fork_job(
                'calibre_plugins.remarkable_sync.worker',
                'convert_epub_to_pdf',
                args=(path, title, device_type, font_family, font_size, line_height,
                      margin_left, margin_right, margin_top, margin_bottom,
                      footer_template),
                timeout=600
            )

            data = result.get('result') if result else None
            if not data:
                return (False, f'{title}: Conversion worker failed', None)
            if not data['success']:
                return (False, f'{title}: Conversion failed - {data.get("error", "Unknown error")}', None)

            pdf_path = data['pdf_path']
            temp_dir = os.path.dirname(pdf_path)
            shutil.copy2(pdf_path, output_path)
            return (True, f"Exported '{title}'", output_path)

        return (False, f'{title}: Unsupported format {fmt}', None)

    except Exception as e:
        return (False, f'{title}: {str(e)}', None)

    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass
