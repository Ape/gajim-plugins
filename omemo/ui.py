# -*- coding: utf-8 -*-
#
# Copyright 2015 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
# Copyright 2015 Daniel Gultsch <daniel@cgultsch.de>
#
# This file is part of Gajim-OMEMO plugin.
#
# The Gajim-OMEMO plugin is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# Gajim-OMEMO is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# the Gajim-OMEMO plugin.  If not, see <http://www.gnu.org/licenses/>.
#

import logging

import gtk
from common import gajim
from plugins.gui import GajimPluginConfigDialog
import gobject
import binascii

log = logging.getLogger('gajim.plugin_system.omemo')

# from plugins.helpers import log


class PreKeyButton(gtk.Button):
    def __init__(self, plugin, contact):
        super(PreKeyButton, self).__init__(label='Get Device Keys' + str(
            plugin.are_keys_missing(contact)))
        self.plugin = plugin
        self.contact = contact
        self.connect('clicked', self.on_click)
        self.refresh()

    def refresh(self):
        amount = self.plugin.are_keys_missing(self.contact)
        if amount == 0:
            self.set_no_show_all(True)
            self.hide()
        else:
            self.set_no_show_all(False)
            self.show()
        self.set_label('Get Device Keys ' + str(amount))

    def on_click(self, widget):
        self.plugin.query_prekey(self.contact)


class ClearDevicesButton(gtk.Button):
    def __init__(self, plugin, contact):
        super(ClearDevicesButton, self).__init__(label='Clear Devices')
        self.plugin = plugin
        self.contact = contact
        self.connect('clicked', self.on_click)

    def on_click(self, widget):
        self.plugin.clear_device_list(self.contact)


class Checkbox(gtk.CheckButton):
    def __init__(self, plugin, chat_control):
        super(Checkbox, self).__init__(label='OMEMO')
        self.chat_control = chat_control
        self.contact = chat_control.contact
        self.plugin = plugin
        self.connect('clicked', self.on_click)

    def on_click(self, widget):
        enabled = self.get_active()
        if enabled:
            log.info(self.contact.account.name + ' ⇒ Enable OMEMO for ' +
                     self.contact.jid)
            self.plugin.omemo_enable_for(self.contact)
            self.chat_control._show_lock_image(True, 'OMEMO',
                                               True, True, False)
            self.chat_control.print_conversation_line(
                u'OMEMO encryption enabled ', 'status', '', None)
        else:
            log.info(self.contact.account.name + ' ⇒ Disable OMEMO for ' +
                     self.contact.jid)
            self.plugin.omemo_disable_for(self.contact)
            self.chat_control._show_lock_image(False, 'OMEMO', False, True,
                                               False)
            self.chat_control.print_conversation_line(
                u'OMEMO encryption disabled', 'status', '', None)


def _add_widget(widget, chat_control):
    actions_hbox = chat_control.xml.get_object('actions_hbox')
    send_button = chat_control.xml.get_object('send_button')
    send_button_pos = actions_hbox.child_get_property(send_button, 'position')
    actions_hbox.add_with_properties(widget, 'position', send_button_pos - 2,
                                     'expand', False)
    widget.show_all()


class Ui(object):

    def __init__(self, plugin, chat_control, enabled):
        self.contact = chat_control.contact
        self.chat_control = chat_control
        self.prekey_button = PreKeyButton(plugin, self.contact)
        self.checkbox = Checkbox(plugin, chat_control)
        self.clear_button = ClearDevicesButton(plugin, self.contact)

        if enabled:
            self.checkbox.set_active(True)
        else:
            self.encryption_disable()

        _add_widget(self.prekey_button, self.chat_control)
        _add_widget(self.checkbox, self.chat_control)
        _add_widget(self.clear_button, self.chat_control)

    def encryption_active(self):
        return self.checkbox.get_active()

    def encryption_disable(self):
        if self.checkbox.get_active():
            self.checkbox.set_active(False)
        else:
            log.info(self.contact.account.name + ' ⇒ Disable OMEMO for ' +
                     self.contact.jid)
            self.chat_control._show_lock_image(False, 'OMEMO', False, True,
                                               False)
            self.chat_control.print_conversation_line(
                u'OMEMO encryption disabled', 'status', '', None)

    def activate_omemo(self):
        if not self.checkbox.get_active():
            self.checkbox.set_active(True)

    def plain_warning(self):
        self.chat_control.print_conversation_line(
            'Received plaintext message! ' +
            'Your next message will still be encrypted!', 'status', '', None)

    def update_prekeys(self):
        self.prekey_button.refresh()


class OMEMOConfigDialog(GajimPluginConfigDialog):
    def init(self):
        self.GTK_BUILDER_FILE_PATH = \
            self.plugin.local_file_path('config_dialog.ui')
        self.B = gtk.Builder()
        self.B.set_translation_domain('gajim_plugins')
        self.B.add_from_file(self.GTK_BUILDER_FILE_PATH)

        self.fpr_model = gtk.ListStore(gobject.TYPE_INT,
                                       gobject.TYPE_STRING,
                                       gobject.TYPE_STRING,
                                       gobject.TYPE_STRING)

        self.account_store = self.B.get_object('account_store')

        for account in sorted(gajim.contacts.get_accounts()):
            self.account_store.append(row=(account,))

        self.fpr_view = self.B.get_object('fingerprint_view')
        self.fpr_view.set_model(self.fpr_model)
        self.fpr_view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)

        if len(self.account_store) > 0:
            self.B.get_object('account_combobox').set_active(0)

        self.child.pack_start(self.B.get_object('notebook1'))

        self.B.connect_signals(self)

    def on_run(self):
        self.update_context_list()
        self.account_combobox_changed_cb(self.B.get_object('account_combobox'))

    def account_combobox_changed_cb(self, box, *args):
        self.update_context_list()

    def trust_button_clicked_cb(self, button, *args):
        active = self.B.get_object('account_combobox').get_active()
        account = self.account_store[active][0]

        state = self.plugin.get_omemo_state(account)

        mod, paths = self.fpr_view.get_selection().get_selected_rows()

        for path in paths:
            it = mod.get_iter(path)
            _id, user, fpr = mod.get(it, 0, 1, 3)

            dlg = gtk.Dialog('Confirm trusting fingerprint', self,
                             gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                             (gtk.STOCK_YES, gtk.RESPONSE_YES,
                              gtk.STOCK_NO, gtk.RESPONSE_NO))
            l = gtk.Label()
            l.set_markup('Are you sure you want to trust the following '
                         'fingerprint for the contact %s on the account %s?'
                         '\n\n%s' % (user, account, fpr))
            l.set_line_wrap(True)
            dlg.vbox.pack_start(l)
            dlg.show_all()

            if dlg.run() == gtk.RESPONSE_YES:
                    state.store.identityKeyStore.setTrust(_id, 1)
            dlg.destroy()

        self.update_context_list()

    def untrust_button_clicked_cb(self, button, *args):
        active = self.B.get_object('account_combobox').get_active()
        account = self.account_store[active][0]

        state = self.plugin.get_omemo_state(account)

        mod, paths = self.fpr_view.get_selection().get_selected_rows()

        for path in paths:
            it = mod.get_iter(path)
            _id, user, fpr = mod.get(it, 0, 1, 3)

            dlg = gtk.Dialog('Confirm trusting fingerprint', self,
                             gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                             (gtk.STOCK_YES, gtk.RESPONSE_YES,
                              gtk.STOCK_NO, gtk.RESPONSE_NO))
            l = gtk.Label()
            l.set_markup('Are you sure you want to NOT trust the following '
                         'fingerprint for the contact %s on the account %s?'
                         '\n\n%s' % (user, account, fpr))
            l.set_line_wrap(True)
            dlg.vbox.pack_start(l)
            dlg.show_all()

            if dlg.run() == gtk.RESPONSE_YES:
                    state.store.identityKeyStore.setTrust(_id, 0)
            dlg.destroy()

        self.update_context_list()

    def fpr_button_pressed_cb(self, tw, event):
        if event.button == 3:
            pthinfo = tw.get_path_at_pos(int(event.x), int(event.y))

            if pthinfo is None:
                # only show the popup when we right clicked on list content
                # ie. don't show it when we click at empty rows
                return False

            # if the row under the mouse is already selected, we keep the
            # selection, otherwise we only select the new item
            keep_selection = tw.get_selection().path_is_selected(pthinfo[0])

            pop = self.B.get_object('fprclipboard_menu')
            pop.popup(None, None, None, event.button, event.time)

            # keep_selection=True -> no further processing of click event
            # keep_selection=False-> further processing -> GTK usually selects
            #   the item below the cursor
            return keep_selection

    def clipboard_button_cb(self, menuitem):
        mod, paths = self.fpr_view.get_selection().get_selected_rows()

        fprs = []
        for path in paths:
            it = mod.get_iter(path)
            jid, fpr = mod.get(it, 1, 3)
            fprs.append('%s: %s' % (jid, fpr[4:-5]))
        gtk.Clipboard().set_text('\n'.join(fprs))
        gtk.Clipboard(selection='PRIMARY').set_text('\n'.join(fprs))

    def update_context_list(self):
        trust = {None: "Not Set", 0: False, 1: True}
        self.fpr_model.clear()
        active = self.B.get_object('account_combobox').get_active()
        account = self.account_store[active][0]
        state = self.plugin.get_omemo_state(account)

        ownfpr = binascii.hexlify(state.store.getIdentityKeyPair()
                                  .getPublicKey().serialize())
        self.B.get_object('fingerprint_label').set_markup('<tt>%s</tt>'
                                                          % ownfpr[2:])

        fprDB = state.store.identityKeyStore.getAllFingerprints()
        for item in fprDB:
            _id = item[0]
            jid = item[1]
            fpr = binascii.hexlify(item[2])
            self.fpr_model.append((_id, jid, trust[item[3]],
                                   '<tt>%s</tt>' % fpr[2:]))
