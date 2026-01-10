#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main module for reMarkable Sync plugin.

This module provides utilities for the UI layer. The actual conversion
and sending logic is in worker.py.
"""

import os


def get_book_path(db, book_id):
    """Get path to book file using Calibre's new API.

    Returns (format, path) tuple. Prefers PDF over EPUB.

    Args:
        db: Calibre database (new API)
        book_id: Book ID

    Returns:
        tuple: (format_name, file_path) or (None, None) if no suitable format
    """
    # Try to get PDF format first
    if db.has_format(book_id, 'PDF'):
        fmt = db.format_abspath(book_id, 'PDF')
        if fmt and os.path.exists(fmt):
            return ('PDF', fmt)

    # Try EPUB
    if db.has_format(book_id, 'EPUB'):
        fmt = db.format_abspath(book_id, 'EPUB')
        if fmt and os.path.exists(fmt):
            return ('EPUB', fmt)

    return (None, None)
