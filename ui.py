#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5.Qt import (QMenu, QIcon, QProgressDialog, QApplication, Qt,
                       QMessageBox, QThread, QFileDialog, pyqtSignal)

from calibre.gui2.actions import InterfaceAction
from calibre.gui2 import error_dialog, info_dialog

from calibre_plugins.remarkable_sync.main import get_book_path
from calibre_plugins.remarkable_sync.config import prefs


class SendWorkerThread(QThread):
    """Worker thread for sending books to reMarkable without blocking the UI."""

    progress_update = pyqtSignal(int, str)  # (index, label_text)
    book_finished = pyqtSignal(bool, str, object, int)  # (success, message, doc_uuid, book_id)
    ask_existing = pyqtSignal(int, str, dict)  # (index, title, existing_doc)
    all_done = pyqtSignal()

    def __init__(self, books, folder_uuid, device_type, font_family, font_size,
                 line_height, margin_left, margin_right, margin_top, margin_bottom,
                 footer_template, auto_convert):
        QThread.__init__(self)
        self.books = books
        self.folder_uuid = folder_uuid
        self.device_type = device_type
        self.font_family = font_family
        self.font_size = font_size
        self.line_height = line_height
        self.margin_left = margin_left
        self.margin_right = margin_right
        self.margin_top = margin_top
        self.margin_bottom = margin_bottom
        self.footer_template = footer_template
        self.auto_convert = auto_convert

        self._cancelled = False
        self._existing_reply = None  # Set by main thread via slot
        self._waiting_for_reply = False

    def cancel(self):
        self._cancelled = True

    def set_existing_reply(self, reply):
        """Called from main thread to answer the existing-document question."""
        self._existing_reply = reply
        self._waiting_for_reply = False

    def run(self):
        from calibre_plugins.remarkable_sync.worker import process_single_book, check_existing_document

        for i, book in enumerate(self.books):
            if self._cancelled:
                break

            title = book['title']
            self.progress_update.emit(i, f"Checking ({i+1}/{len(self.books)}): {title}")

            # Check if document already exists
            update_existing = False
            existing_uuid = None
            existing_doc = check_existing_document(title, self.folder_uuid)

            if existing_doc:
                # Ask the main thread what to do
                self._waiting_for_reply = True
                self._existing_reply = None
                self.ask_existing.emit(i, title, existing_doc)

                # Wait for the main thread to respond
                while self._waiting_for_reply and not self._cancelled:
                    self.msleep(50)

                if self._cancelled:
                    break

                reply = self._existing_reply
                if reply == 'cancel':
                    break
                elif reply == 'skip':
                    self.book_finished.emit(False, 'skipped', None, book['book_id'])
                    continue
                else:  # 'update'
                    update_existing = True
                    existing_uuid = existing_doc['uuid']

            self.progress_update.emit(i, f"Processing ({i+1}/{len(self.books)}): {title}")

            success, message, doc_uuid = process_single_book(
                book, self.folder_uuid, self.device_type, self.font_family,
                self.font_size, self.line_height,
                self.margin_left, self.margin_right, self.margin_top, self.margin_bottom,
                self.footer_template, self.auto_convert,
                update_existing=update_existing, existing_uuid=existing_uuid
            )

            self.book_finished.emit(success, message, doc_uuid, book['book_id'])

            if self._cancelled:
                break

        self.all_done.emit()


class ExportWorkerThread(QThread):
    """Worker thread for exporting books as PDF without blocking the UI."""

    progress_update = pyqtSignal(int, str)
    book_finished = pyqtSignal(bool, str, str)  # (success, message, output_path)
    all_done = pyqtSignal()

    def __init__(self, books, output_dir, device_type, font_family, font_size,
                 line_height, margin_left, margin_right, margin_top, margin_bottom,
                 footer_template, auto_convert):
        QThread.__init__(self)
        self.books = books
        self.output_dir = output_dir
        self.device_type = device_type
        self.font_family = font_family
        self.font_size = font_size
        self.line_height = line_height
        self.margin_left = margin_left
        self.margin_right = margin_right
        self.margin_top = margin_top
        self.margin_bottom = margin_bottom
        self.footer_template = footer_template
        self.auto_convert = auto_convert
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        from calibre_plugins.remarkable_sync.worker import export_single_book

        for i, book in enumerate(self.books):
            if self._cancelled:
                break

            title = book['title']
            self.progress_update.emit(i, f"Processing ({i+1}/{len(self.books)}): {title}")

            success, message, output_path = export_single_book(
                book, self.output_dir, self.device_type, self.font_family,
                self.font_size, self.line_height,
                self.margin_left, self.margin_right, self.margin_top, self.margin_bottom,
                self.footer_template, self.auto_convert,
            )
            self.book_finished.emit(success, message, output_path or '')

        self.all_done.emit()


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

        export_action = self.create_action(
            spec=('Export as PDF...', None,
                  'Export selected books as reMarkable-tuned PDFs', None),
            attr='export_action'
        )
        export_action.triggered.connect(self.export_as_pdf)
        self.menu.addAction(export_action)

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
        from calibre_plugins.remarkable_sync.remarkable import (
            check_remarkable_app_installed, is_remarkable_app_running,
            stop_remarkable_app
        )

        # Check if reMarkable app is installed
        is_installed, message = check_remarkable_app_installed()
        if not is_installed:
            return error_dialog(self.gui, 'reMarkable App Not Found', message, show=True)

        # Get selected book IDs
        ids = self.gui.library_view.get_selected_ids()

        if not ids:
            return error_dialog(self.gui, 'No selection',
                                'No books selected', show=True)

        # Get the database
        self._db = self.gui.current_db.new_api

        books = self._collect_books(ids)

        if not books:
            return error_dialog(self.gui, 'No valid books',
                                'No books with PDF or EPUB format found', show=True)

        # Stop the desktop app only after validation has passed; _on_all_done
        # restarts it unconditionally so cancels and errors don't leave it closed.
        self._app_was_running = is_remarkable_app_running()
        if self._app_was_running:
            stop_remarkable_app()

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

        # Track results
        self._success_count = 0
        self._error_count = 0
        self._skip_count = 0
        self._messages = []

        # Create progress dialog
        self._progress = QProgressDialog(
            'Sending books to reMarkable...',
            'Cancel',
            0, len(books),
            self.gui
        )
        self._progress.setWindowTitle('reMarkable Sync')
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.setAutoClose(False)
        self._progress.setAutoReset(False)
        self._progress.show()

        # Create and start worker thread
        self._worker = SendWorkerThread(
            books, folder_uuid, device_type, font_family, font_size, line_height,
            margin_left, margin_right, margin_top, margin_bottom,
            footer_template, auto_convert
        )
        self._worker.progress_update.connect(self._on_progress_update)
        self._worker.book_finished.connect(self._on_book_finished)
        self._worker.ask_existing.connect(self._on_ask_existing)
        self._worker.all_done.connect(self._on_all_done)
        self._progress.canceled.connect(self._worker.cancel)
        self._worker.start()

    def _on_progress_update(self, index, label_text):
        self._progress.setValue(index)
        self._progress.setLabelText(label_text)

    def _on_book_finished(self, success, message, doc_uuid, book_id):
        if message == 'skipped':
            self._skip_count += 1
            return

        if success:
            self._success_count += 1
            col_rm_uuid = prefs.get('col_rm_uuid', '')
            if col_rm_uuid and doc_uuid:
                try:
                    self._db.set_field(col_rm_uuid, {book_id: doc_uuid})
                except Exception:
                    pass
        else:
            self._error_count += 1
            self._messages.append(message)

    def _on_ask_existing(self, index, title, existing_doc):
        """Handle existing document question on main thread."""
        self._progress.hide()
        reply = QMessageBox.question(
            self.gui,
            'Document Exists',
            f"'{title}' already exists on reMarkable.\n\n"
            "Do you want to update it? (Only the PDF will be replaced, "
            "annotations and reading position will be preserved.)",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes
        )
        self._progress.show()

        if reply == QMessageBox.Cancel:
            self._worker.set_existing_reply('cancel')
        elif reply == QMessageBox.No:
            self._worker.set_existing_reply('skip')
        else:
            self._worker.set_existing_reply('update')

    def _on_all_done(self):
        """Handle completion of all book processing."""
        from calibre_plugins.remarkable_sync.remarkable import start_remarkable_app

        self._progress.setValue(self._progress.maximum())
        self._progress.close()

        success_count = self._success_count
        error_count = self._error_count
        skip_count = self._skip_count
        messages = self._messages
        app_was_running = self._app_was_running

        # Always restart the desktop app if we stopped it, so cancels and
        # error-only runs don't leave the user without their app.
        if app_was_running:
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
            info_dialog(self.gui, 'Skipped',
                        f"Skipped {skip_count} existing book(s). No new books sent.",
                        show=True)
        elif error_count > 0:
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

    def _collect_books(self, ids):
        """Build the list of book dicts consumed by the worker threads."""
        books = []
        for book_id in ids:
            mi = self._db.get_metadata(book_id)
            fmt, path = get_book_path(self._db, book_id)
            if not (fmt and path):
                continue

            author = mi.authors[0] if mi.authors else None
            display_title = mi.title
            if mi.series:
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
        return books

    def export_as_pdf(self):
        """Export selected books as reMarkable-tuned PDFs to a chosen folder."""
        ids = self.gui.library_view.get_selected_ids()
        if not ids:
            return error_dialog(self.gui, 'No selection',
                                'No books selected', show=True)

        self._db = self.gui.current_db.new_api
        books = self._collect_books(ids)
        if not books:
            return error_dialog(self.gui, 'No valid books',
                                'No books with PDF or EPUB format found', show=True)

        output_dir = QFileDialog.getExistingDirectory(
            self.gui, 'Choose folder to save PDFs', ''
        )
        if not output_dir:
            return

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

        self._export_success = 0
        self._export_errors = 0
        self._export_messages = []
        self._export_output_dir = output_dir

        self._export_progress = QProgressDialog(
            'Exporting books as PDF...', 'Cancel', 0, len(books), self.gui
        )
        self._export_progress.setWindowTitle('reMarkable Sync')
        self._export_progress.setWindowModality(Qt.WindowModal)
        self._export_progress.setMinimumDuration(0)
        self._export_progress.setAutoClose(False)
        self._export_progress.setAutoReset(False)
        self._export_progress.show()

        self._export_worker = ExportWorkerThread(
            books, output_dir, device_type, font_family, font_size, line_height,
            margin_left, margin_right, margin_top, margin_bottom,
            footer_template, auto_convert,
        )
        self._export_worker.progress_update.connect(self._on_export_progress)
        self._export_worker.book_finished.connect(self._on_export_book_finished)
        self._export_worker.all_done.connect(self._on_export_done)
        self._export_progress.canceled.connect(self._export_worker.cancel)
        self._export_worker.start()

    def _on_export_progress(self, index, label_text):
        self._export_progress.setValue(index)
        self._export_progress.setLabelText(label_text)

    def _on_export_book_finished(self, success, message, output_path):
        if success:
            self._export_success += 1
        else:
            self._export_errors += 1
            self._export_messages.append(message)

    def _on_export_done(self):
        self._export_progress.setValue(self._export_progress.maximum())
        self._export_progress.close()

        if self._export_success > 0:
            msg = (f"Exported {self._export_success} PDF(s) to\n"
                   f"{self._export_output_dir}")
            if self._export_errors > 0:
                msg += (f"\n\nFailed to export {self._export_errors} book(s):\n"
                        + "\n".join(self._export_messages[:5]))
            info_dialog(self.gui, 'Export Complete', msg, show=True)
        elif self._export_errors > 0:
            error_dialog(
                self.gui, 'Export Failed',
                "No books were exported.\n\n" + "\n".join(self._export_messages[:5]),
                show=True
            )
