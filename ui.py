#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5.Qt import QMenu, QIcon, QProgressDialog, QApplication, Qt, QMessageBox

from calibre.gui2.actions import InterfaceAction
from calibre.gui2 import error_dialog, info_dialog

from calibre_plugins.remarkable_sync.main import get_book_path
from calibre_plugins.remarkable_sync.config import prefs


class ReMarkableSyncAction(InterfaceAction):
    name = 'reMarkable Sync'
    action_spec = ('reMarkable Sync', None, 'Send books to reMarkable tablet', None)
    action_type = 'current'

    def genesis(self):
        # Load plugin icon
        icon = get_icons('images/icon.png', 'reMarkable Sync')
        self.qaction.setIcon(icon)

        # Default action: Send to reMarkable
        self.qaction.triggered.connect(self.send_to_remarkable)

        # Create dropdown menu for additional actions
        self.menu = QMenu(self.gui)
        self.qaction.setMenu(self.menu)

        self.create_menu_actions()

    def create_menu_actions(self):
        """Create menu actions"""
        send_action = self.create_action(
            spec=('Send to reMarkable', None, 'Send selected books to reMarkable', None),
            attr='send_action'
        )
        send_action.triggered.connect(self.send_to_remarkable)
        self.menu.addAction(send_action)

        self.menu.addSeparator()

        sync_action = self.create_action(
            spec=('Sync Reading Positions', None, 'Sync reading positions from reMarkable', None),
            attr='sync_action'
        )
        sync_action.triggered.connect(self.sync_positions)
        self.menu.addAction(sync_action)

        self.menu.addSeparator()

        settings_action = self.create_action(
            spec=('Settings...', None, 'Configure reMarkable Sync plugin', None),
            attr='settings_action'
        )
        settings_action.triggered.connect(self.show_settings)
        self.menu.addAction(settings_action)

    def send_to_remarkable(self):
        """Send selected books to reMarkable"""
        from calibre_plugins.remarkable_sync.worker import process_single_book, check_existing_document
        from calibre_plugins.remarkable_sync.remarkable import (
            check_remarkable_app_installed, is_remarkable_app_running,
            stop_remarkable_app, start_remarkable_app
        )

        # Check if reMarkable app is installed
        is_installed, message = check_remarkable_app_installed()
        if not is_installed:
            return error_dialog(self.gui, 'reMarkable App Not Found', message, show=True)

        # Check if app was running (we'll restart it after sync)
        app_was_running = is_remarkable_app_running()
        if app_was_running:
            stop_remarkable_app()

        # Get selected book IDs
        ids = self.gui.library_view.get_selected_ids()

        if not ids:
            return error_dialog(self.gui, 'No selection',
                                'No books selected', show=True)

        # Get the database
        db = self.gui.current_db.new_api

        # Collect book info
        books = []
        for book_id in ids:
            mi = db.get_metadata(book_id)
            fmt, path = get_book_path(db, book_id)
            if fmt and path:
                # Format title as "Series-Number Title - Author"
                author = mi.authors[0] if mi.authors else None
                display_title = mi.title
                if mi.series:
                    # Format series index as integer if whole number, else keep decimal
                    idx = int(mi.series_index) if mi.series_index == int(mi.series_index) else mi.series_index
                    display_title = f"{mi.series}-{idx} {mi.title}"
                if author:
                    display_title = f"{display_title} - {author}"

                books.append({
                    'book_id': book_id,
                    'title': display_title,
                    'author': author,
                    'format': fmt,
                    'path': path,
                })

        if not books:
            return error_dialog(self.gui, 'No valid books',
                                'No books with PDF or EPUB format found', show=True)

        # Get settings
        folder_uuid = prefs.get('default_folder_uuid', '')
        device_type = prefs.get('device_type', 'rmpp')
        font_family = prefs.get('pdf_font_family', '')
        font_size = prefs.get('pdf_font_size', 12.0)
        line_height = prefs.get('pdf_line_height', 125)
        margin_left = prefs.get('pdf_margin_left', 15)
        margin_right = prefs.get('pdf_margin_right', 15)
        margin_top = prefs.get('pdf_margin_top', 45)
        margin_bottom = prefs.get('pdf_margin_bottom', 35)
        footer_template = prefs.get('pdf_footer_template', '')
        auto_convert = prefs.get('auto_convert_epub', True)

        # Create progress dialog
        progress = QProgressDialog(
            'Sending books to reMarkable...',
            'Cancel',
            0, len(books),
            self.gui
        )
        progress.setWindowTitle('reMarkable Sync')
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()
        QApplication.processEvents()

        success_count = 0
        error_count = 0
        messages = []

        skip_count = 0

        for i, book in enumerate(books):
            if progress.wasCanceled():
                messages.append('Operation cancelled by user')
                break

            title = book['title']
            progress.setLabelText(f"Checking ({i+1}/{len(books)}): {title}")
            progress.setValue(i)
            QApplication.processEvents()

            # Check if document already exists
            update_existing = False
            existing_uuid = None
            existing_doc = check_existing_document(title, folder_uuid)

            if existing_doc:
                progress.hide()
                reply = QMessageBox.question(
                    self.gui,
                    'Document Exists',
                    f"'{title}' already exists on reMarkable.\n\n"
                    "Do you want to update it? (Only the PDF will be replaced, "
                    "annotations and reading position will be preserved.)",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                    QMessageBox.Yes
                )
                progress.show()
                QApplication.processEvents()

                if reply == QMessageBox.Cancel:
                    messages.append('Operation cancelled by user')
                    break
                elif reply == QMessageBox.No:
                    skip_count += 1
                    continue
                else:
                    update_existing = True
                    existing_uuid = existing_doc['uuid']

            progress.setLabelText(f"Processing ({i+1}/{len(books)}): {title}")
            QApplication.processEvents()

            # Process book using fork_job (runs in separate process)
            success, message, doc_uuid = process_single_book(
                book, folder_uuid, device_type, font_family, font_size, line_height,
                margin_left, margin_right, margin_top, margin_bottom,
                footer_template, auto_convert,
                update_existing=update_existing, existing_uuid=existing_uuid
            )

            if success:
                success_count += 1
                # Store reMarkable UUID in custom column if configured
                col_rm_uuid = prefs.get('col_rm_uuid', '')
                if col_rm_uuid and doc_uuid:
                    try:
                        db.set_field(col_rm_uuid, {book['book_id']: doc_uuid})
                    except Exception:
                        pass  # Don't fail the whole operation if UUID storage fails
            else:
                error_count += 1
                messages.append(message)

        progress.setValue(len(books))
        progress.close()

        # Restart reMarkable app if it was running
        if app_was_running and success_count > 0:
            start_remarkable_app()

        # Show results
        if success_count > 0:
            msg = f"Successfully sent {success_count} book(s) to reMarkable."

            if app_was_running:
                msg += "\n\nThe reMarkable app has been restarted to sync your books."
            else:
                msg += "\n\nStart the reMarkable desktop app to sync to your device."

            if skip_count > 0:
                msg += f"\n\nSkipped {skip_count} existing book(s)."

            if error_count > 0:
                msg += f"\n\nFailed to send {error_count} book(s):\n"
                msg += "\n".join(messages[:5])

            info_dialog(self.gui, 'Success', msg, show=True)
        elif skip_count > 0 and error_count == 0:
            # Restart app even if only skipped (user might have updated)
            if app_was_running:
                start_remarkable_app()
            info_dialog(self.gui, 'Skipped',
                        f"Skipped {skip_count} existing book(s). No new books sent.",
                        show=True)
        elif error_count > 0:
            # Restart app even on errors
            if app_was_running:
                start_remarkable_app()
            error_dialog(self.gui, 'Error',
                         f"Failed to send book(s):\n" + "\n".join(messages[:5]),
                         show=True)

    def sync_positions(self):
        """Sync reading positions from reMarkable to Calibre custom columns"""
        from calibre_plugins.remarkable_sync.remarkable import get_all_documents_with_progress

        # UUID column is required for sync
        col_rm_uuid = prefs.get('col_rm_uuid', '')
        if not col_rm_uuid:
            return error_dialog(
                self.gui, 'UUID Column Required',
                'Please configure the reMarkable UUID column in Settings first.\n\n'
                'This column stores the document ID and is required to safely sync positions.',
                show=True
            )

        col_progress = prefs.get('col_progress', '')
        col_page = prefs.get('col_page', '')
        col_last_read = prefs.get('col_last_read', '')

        if not any([col_progress, col_page, col_last_read]):
            return error_dialog(
                self.gui, 'No Columns Configured',
                'Please configure at least one column for Progress, Current Page, or Last Read.',
                show=True
            )

        # Get documents from the configured reMarkable folder only
        folder_uuid = prefs.get('default_folder_uuid', '')
        rm_documents = get_all_documents_with_progress(folder_uuid)
        if not rm_documents:
            return info_dialog(
                self.gui, 'No Documents',
                'No documents found in the configured reMarkable folder.',
                show=True
            )

        # Build a lookup of reMarkable documents by UUID
        rm_by_uuid = {doc['uuid']: doc for doc in rm_documents}

        # Get the database
        db = self.gui.current_db.new_api

        # Find all books that have a reMarkable UUID set
        book_ids = db.search(f'{col_rm_uuid}:~.+', '')  # Books with non-empty UUID

        synced_count = 0
        not_on_rm = 0

        for book_id in book_ids:
            try:
                book_uuid = db.field_for(col_rm_uuid, book_id)
                if not book_uuid:
                    continue

                # Find matching document on reMarkable
                doc = rm_by_uuid.get(book_uuid)
                if not doc:
                    not_on_rm += 1
                    continue

                # Check if existing data is more recent - skip if so
                if col_last_read and doc['last_read']:
                    existing_date = db.field_for(col_last_read, book_id)
                    if existing_date is not None and existing_date > doc['last_read']:
                        continue  # Skip - existing data is more recent

                if col_progress:
                    db.set_field(col_progress, {book_id: doc['progress']})
                if col_page:
                    db.set_field(col_page, {book_id: doc['page']})
                if col_last_read and doc['last_read']:
                    db.set_field(col_last_read, {book_id: doc['last_read']})
                synced_count += 1
            except Exception:
                pass  # Continue with other books

        # Refresh the GUI to show updated values
        self.gui.library_view.model().refresh()

        # Show results
        msg = f"Synced reading positions for {synced_count} book(s)."
        if not_on_rm > 0:
            msg += f"\n\n{not_on_rm} book(s) not found on reMarkable (may have been deleted)."

        info_dialog(self.gui, 'Sync Complete', msg, show=True)

    def show_settings(self):
        """Open the plugin settings dialog"""
        self.interface_action_base_plugin.do_user_config(self.gui)
