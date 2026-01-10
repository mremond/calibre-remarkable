#!/usr/bin/env python
# -*- coding: utf-8 -*-

__license__ = 'GPL v3'
__copyright__ = '2025, Mickaël Rémond'
__docformat__ = 'restructuredtext en'

from calibre.customize import InterfaceActionBase

class ReMarkableSync(InterfaceActionBase):
    '''
    Plugin to sync books with reMarkable tablet via desktop app
    '''
    
    name = 'reMarkable Sync'
    description = 'Send books to reMarkable Paper Pro Move via desktop app and sync reading positions'
    supported_platforms = ['osx', 'windows', 'linux']
    author = 'Mickaël Rémond'
    version = (0, 1, 0)
    minimum_calibre_version = (5, 0, 0)
    
    actual_plugin = 'calibre_plugins.remarkable_sync.ui:ReMarkableSyncAction'
    
    def is_customizable(self):
        return True
    
    def config_widget(self):
        from calibre_plugins.remarkable_sync.config import ConfigWidget
        from calibre.gui2 import gui_prefs
        cw = ConfigWidget()
        # Try to get database access for custom columns
        try:
            from calibre.gui2.ui import get_gui
            gui = get_gui()
            if gui and hasattr(gui, 'current_db'):
                cw.populate_custom_columns(gui.current_db)
        except Exception:
            pass  # Config can work without db access
        return cw
    
    def save_settings(self, config_widget):
        config_widget.save_settings()
