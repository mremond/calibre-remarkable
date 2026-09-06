#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5.Qt import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                      QCheckBox, QSpinBox, QGroupBox, QLineEdit, QPushButton,
                      QFontDatabase)

from calibre.utils.config import JSONConfig

# Plugin preferences
prefs = JSONConfig('plugins/remarkable_sync')

# Default settings
prefs.defaults['filename_template'] = '{series}{series_index:| - | }{title} - {authors}'
prefs.defaults['default_folder_uuid'] = ''
prefs.defaults['default_folder_name'] = 'Root'
prefs.defaults['device_type'] = 'rmpp'  # Default to Paper Pro
prefs.defaults['auto_convert_epub'] = True
prefs.defaults['pdf_font_family'] = ''  # Empty means use default
prefs.defaults['pdf_font_size'] = 24.0  # In pixels (matching manual conversion)
prefs.defaults['pdf_line_height'] = 125  # percentage
prefs.defaults['pdf_margin_left'] = 15
prefs.defaults['pdf_margin_right'] = 15
prefs.defaults['pdf_margin_top'] = 45
prefs.defaults['pdf_margin_bottom'] = 35
prefs.defaults['pdf_footer_template'] = '''<footer style="justify-content: end; font-size: x-small; color: gray;">
   <div></div>
<script>document.currentScript.parentNode.querySelector("div").innerHTML = "" + (_PAGENUM_ + 1) + " - " + Math.round(_PAGENUM_ * 100 / _TOTAL_PAGES_) + " % "</script>
 </footer>'''

# Custom column settings for reading position sync
prefs.defaults['col_rm_uuid'] = ''  # Column for reMarkable document UUID (required for sync)
prefs.defaults['col_progress'] = ''  # Column for reading progress (0-100%)
prefs.defaults['col_page'] = ''  # Column for current page number
prefs.defaults['col_last_read'] = ''  # Column for last read timestamp

# Font sizes in pixels (matching Calibre's PDF output settings)
RMPP_FONT_SIZES = [9.0, 11.0, 12.0, 13.0, 14.0, 17.0, 19.0, 21.0, 22.0, 24.0, 28.0, 32.0]

# Device types with their screen specifications
# Format: (name, width_px, height_px, dpi)
REMARKABLE_DEVICES = {
    'rmpp': ('reMarkable Paper Pro', 1620, 2160, 229),
    'rmpp_move': ('reMarkable Paper Pro Move', 954, 1696, 229),
    'rm2': ('reMarkable 2', 1404, 1872, 226),
}

def get_device_page_size(device_type):
    """
    Get the page size in pixels for a device type.
    Returns (width, height) in pixels for use with devicepixel unit.
    """
    if device_type not in REMARKABLE_DEVICES:
        device_type = 'rmpp'  # Default to Paper Pro

    _, width_px, height_px, dpi = REMARKABLE_DEVICES[device_type]
    return (width_px, height_px)

class ConfigWidget(QWidget):
    
    def __init__(self):

        QWidget.__init__(self)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        
        # Document Naming
        naming_group = QGroupBox('Document Naming')
        naming_layout = QVBoxLayout()
        
        naming_layout.addWidget(QLabel('Document Name Template:'))
        self.filename_template = QLineEdit()
        self.filename_template.setText(prefs.get('filename_template', '{title}'))
        self.filename_template.setToolTip('Uses standard Calibre template language. Example: {authors} - {title}')
        naming_layout.addWidget(self.filename_template)
        
        naming_group.setLayout(naming_layout)
        self.layout.addWidget(naming_group)
        
        
        # Folder selection
        folder_group = QGroupBox('Upload Settings')
        folder_layout = QVBoxLayout()
        
        folder_label = QLabel('Default folder for new books:')
        folder_layout.addWidget(folder_label)
        
        self.folder_combo = QComboBox()
        self.refresh_folders()
        folder_layout.addWidget(self.folder_combo)
        
        refresh_btn = QPushButton('Refresh Folders')
        refresh_btn.clicked.connect(self.refresh_folders)
        folder_layout.addWidget(refresh_btn)

        # Device type selection
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel('Device type:'))
        self.device_type = QComboBox()
        current_device = prefs['device_type']
        for key, (name, _, _, _) in REMARKABLE_DEVICES.items():
            self.device_type.addItem(name, key)
            if key == current_device:
                self.device_type.setCurrentIndex(self.device_type.count() - 1)
        device_layout.addWidget(self.device_type)
        device_layout.addStretch()
        folder_layout.addLayout(device_layout)

        folder_group.setLayout(folder_layout)
        self.layout.addWidget(folder_group)

        # Conversion settings
        conversion_group = QGroupBox('PDF Conversion Settings')
        conversion_layout = QVBoxLayout()

        self.auto_convert = QCheckBox('Auto-convert EPUB to PDF')
        self.auto_convert.setChecked(prefs['auto_convert_epub'])
        conversion_layout.addWidget(self.auto_convert)

        font_family_layout = QHBoxLayout()
        font_family_layout.addWidget(QLabel('Font family:'))
        self.font_family = QComboBox()
        self.font_family.setEditable(True)  # Allow custom input
        # Add empty option for system default
        self.font_family.addItem('(System default)', '')
        # Populate with available system fonts (static method in Qt5/6)
        current_font = prefs['pdf_font_family']
        current_index = 0
        for i, family in enumerate(sorted(QFontDatabase.families()), 1):
            self.font_family.addItem(family, family)
            if family == current_font:
                current_index = i
        self.font_family.setCurrentIndex(current_index)
        font_family_layout.addWidget(self.font_family)
        conversion_layout.addLayout(font_family_layout)

        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(QLabel('Base font size:'))
        self.font_size = QComboBox()
        current_font_size = prefs['pdf_font_size']
        for size in RMPP_FONT_SIZES:
            self.font_size.addItem(f'{int(size)} px', size)
            if size == current_font_size:
                self.font_size.setCurrentIndex(self.font_size.count() - 1)
        font_size_layout.addWidget(self.font_size)
        font_size_layout.addStretch()
        conversion_layout.addLayout(font_size_layout)

        line_height_layout = QHBoxLayout()
        line_height_layout.addWidget(QLabel('Line height:'))
        self.line_height = QSpinBox()
        self.line_height.setRange(100, 200)
        self.line_height.setSuffix('%')
        self.line_height.setValue(prefs['pdf_line_height'])
        line_height_layout.addWidget(self.line_height)
        line_height_layout.addStretch()
        conversion_layout.addLayout(line_height_layout)

        # Margins
        margins_label = QLabel('Margins (pt):')
        conversion_layout.addWidget(margins_label)

        margins_h_layout = QHBoxLayout()
        margins_h_layout.addWidget(QLabel('Left:'))
        self.margin_left = QSpinBox()
        self.margin_left.setRange(0, 100)
        self.margin_left.setValue(prefs['pdf_margin_left'])
        margins_h_layout.addWidget(self.margin_left)

        margins_h_layout.addWidget(QLabel('Right:'))
        self.margin_right = QSpinBox()
        self.margin_right.setRange(0, 100)
        self.margin_right.setValue(prefs['pdf_margin_right'])
        margins_h_layout.addWidget(self.margin_right)
        margins_h_layout.addStretch()
        conversion_layout.addLayout(margins_h_layout)

        margins_v_layout = QHBoxLayout()
        margins_v_layout.addWidget(QLabel('Top:'))
        self.margin_top = QSpinBox()
        self.margin_top.setRange(0, 100)
        self.margin_top.setValue(prefs['pdf_margin_top'])
        margins_v_layout.addWidget(self.margin_top)

        margins_v_layout.addWidget(QLabel('Bottom:'))
        self.margin_bottom = QSpinBox()
        self.margin_bottom.setRange(0, 100)
        self.margin_bottom.setValue(prefs['pdf_margin_bottom'])
        margins_v_layout.addWidget(self.margin_bottom)
        margins_v_layout.addStretch()
        conversion_layout.addLayout(margins_v_layout)

        conversion_group.setLayout(conversion_layout)
        self.layout.addWidget(conversion_group)
        
        # Sync settings
        sync_group = QGroupBox('Sync Settings')
        sync_layout = QVBoxLayout()

        sync_layout.addWidget(QLabel('Custom columns for reading position (create in Preferences → Add your own columns):'))

        col_uuid_layout = QHBoxLayout()
        col_uuid_layout.addWidget(QLabel('reMarkable UUID:'))
        self.col_rm_uuid = QComboBox()
        col_uuid_layout.addWidget(self.col_rm_uuid)
        col_uuid_layout.addStretch()
        sync_layout.addLayout(col_uuid_layout)

        col_progress_layout = QHBoxLayout()
        col_progress_layout.addWidget(QLabel('Progress (%):'))
        self.col_progress = QComboBox()
        col_progress_layout.addWidget(self.col_progress)
        col_progress_layout.addStretch()
        sync_layout.addLayout(col_progress_layout)

        col_page_layout = QHBoxLayout()
        col_page_layout.addWidget(QLabel('Current page:'))
        self.col_page = QComboBox()
        col_page_layout.addWidget(self.col_page)
        col_page_layout.addStretch()
        sync_layout.addLayout(col_page_layout)

        col_last_read_layout = QHBoxLayout()
        col_last_read_layout.addWidget(QLabel('Last read:'))
        self.col_last_read = QComboBox()
        col_last_read_layout.addWidget(self.col_last_read)
        col_last_read_layout.addStretch()
        sync_layout.addLayout(col_last_read_layout)

        # Store reference to populate later (needs db access)
        self._column_combos = {
            'col_rm_uuid': (self.col_rm_uuid, ['text']),
            'col_progress': (self.col_progress, ['float', 'int']),
            'col_page': (self.col_page, ['int']),
            'col_last_read': (self.col_last_read, ['datetime', 'text']),
        }

        sync_group.setLayout(sync_layout)
        self.layout.addWidget(sync_group)
        
        self.layout.addStretch()
    
    def refresh_folders(self):
        """Refresh folder list from reMarkable"""
        from calibre_plugins.remarkable_sync.remarkable import get_root_folders
        
        self.folder_combo.clear()
        self.folder_combo.addItem('Root', '')
        
        folders = get_root_folders()
        current_uuid = prefs['default_folder_uuid']
        current_index = 0
        
        for i, folder in enumerate(folders, 1):
            pin_marker = '📌 ' if folder.get('pinned') else ''
            display_name = f"{pin_marker}{folder['name']}"
            self.folder_combo.addItem(display_name, folder['uuid'])
            
            if folder['uuid'] == current_uuid:
                current_index = i
        
        self.folder_combo.setCurrentIndex(current_index)
    
    def populate_custom_columns(self, db):
        """Populate custom column dropdowns from database"""
        if db is None:
            return

        custom_columns = db.field_metadata.custom_field_metadata()

        for pref_key, (combo, allowed_types) in self._column_combos.items():
            combo.clear()
            combo.addItem('(None)', '')

            current_value = prefs.get(pref_key, '')
            current_index = 0

            for col_name, col_meta in custom_columns.items():
                col_type = col_meta.get('datatype', '')
                if col_type in allowed_types:
                    display_name = col_meta.get('name', col_name)
                    combo.addItem(f"{display_name} ({col_type})", col_name)
                    if col_name == current_value:
                        current_index = combo.count() - 1

            combo.setCurrentIndex(current_index)

    def save_settings(self):
        """Save settings"""
        prefs['filename_template'] = self.filename_template.text()
        prefs['default_folder_uuid'] = self.folder_combo.currentData()
        prefs['default_folder_name'] = self.folder_combo.currentText()
        prefs['device_type'] = self.device_type.currentData()
        prefs['auto_convert_epub'] = self.auto_convert.isChecked()
        prefs['pdf_font_family'] = self.font_family.currentData() or self.font_family.currentText()
        prefs['pdf_font_size'] = self.font_size.currentData()
        prefs['pdf_line_height'] = self.line_height.value()
        prefs['pdf_margin_left'] = self.margin_left.value()
        prefs['pdf_margin_right'] = self.margin_right.value()
        prefs['pdf_margin_top'] = self.margin_top.value()
        prefs['pdf_margin_bottom'] = self.margin_bottom.value()
        prefs['col_rm_uuid'] = self.col_rm_uuid.currentData() or ''
        prefs['col_progress'] = self.col_progress.currentData() or ''
        prefs['col_page'] = self.col_page.currentData() or ''
        prefs['col_last_read'] = self.col_last_read.currentData() or ''
