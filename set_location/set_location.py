# -*- coding: utf-8 -*-
##

from datetime import datetime
import time
import gtk
import os

from plugins.gui import GajimPluginConfigDialog
from plugins import GajimPlugin
from plugins.helpers import log, log_calls
from common import gajim
import gtkgui_helpers
from dialogs import InputDialog


class SetLocationPlugin(GajimPlugin):
    @log_calls('SetLocationPlugin')
    def init(self):
        self.description = _('Set information about the current geographical '
            'or physical location.\n'
            'To be able to specify a location on the built-in card, '
            'you must install python-osmgpsmap > 0.5')
        self.config_dialog = SetLocationPluginConfigDialog(self)
        self.config_default_values = {
            'alt': (1609, ''),
            'area': ('Central Park', ''),
            'building': ('The Empire State Building', ''),
            'country': ('United States', ''),
            'countrycode': ('US', ''),
            'description': ('Bill\'s house', ''),
            'floor': ('102', ''),
            'lat': (39.75, ''),
            'locality': ('New York City', ''),
            'lon': (-104.99, ''),
            'postalcode': ('10027', ''),
            'region': ('New York', ''),
            'room': ('Observatory', ''),
            'street': ('34th and Broadway', ''),
            'text': ('Northwest corner of the lobby', ''),
            'uri': ('http://beta.plazes.com/plazes/1940:jabber_inc', ''),
            'presets': ({'default': {}}, ''), }

    @log_calls('SetLocationPlugin')
    def activate(self):
        self._data = {}
        timestamp = time.time()
        timestamp = datetime.utcfromtimestamp(timestamp)
        timestamp = timestamp.strftime('%Y-%m-%dT%H:%MZ')
        self._data['timestamp'] = timestamp
        for name in self.config_default_values:
            self._data[name] = self.config[name]
        for acct in gajim.connections:
            if gajim.connections[acct].connected == 0:
                gajim.connections[acct].to_be_sent_location = self._data
            else:
                gajim.connections[acct].send_location(self._data)

    @log_calls('SetLocationPlugin')
    def deactivate(self):
        self._data = {}
        for acct in gajim.connections:
            gajim.connections[acct].send_location(self._data)


class SetLocationPluginConfigDialog(GajimPluginConfigDialog):
    def init(self):
        self.GTK_BUILDER_FILE_PATH = self.plugin.local_file_path(
                'config_dialog.ui')
        self.xml = gtk.Builder()
        self.xml.set_translation_domain('gajim_plugins')
        self.xml.add_objects_from_file(self.GTK_BUILDER_FILE_PATH,
                ['hbox1'])
        hbox = self.xml.get_object('hbox1')
        self.child.pack_start(hbox)
        self.xml.connect_signals(self)
        self.connect('hide', self.on_hide)
        self.is_active = None

        self.preset_combo = self.xml.get_object('preset_combobox')
        self.preset_liststore = gtk.ListStore(str)
        self.preset_combo.set_model(self.preset_liststore)
        cellrenderer = gtk.CellRendererText()
        self.preset_combo.pack_start(cellrenderer, True)
        self.preset_combo.add_attribute(cellrenderer, 'text', 0)
        #self.plugin.config['presets'] = {'default': {}}

    @log_calls('SetLocationPlugin.SetLocationPluginConfigDialog')
    def on_run(self):
        no_map = None
        if not self.is_active:
            pres_keys = sorted(self.plugin.config['presets'].keys())
            for key in pres_keys:
                self.preset_liststore.append((key,))

        for name in self.plugin.config_default_values:
            if name == 'presets':
                continue
            widget = self.xml.get_object(name)
            widget.set_text(str(self.plugin.config[name]))

        try:
            import osmgpsmap
            if osmgpsmap.__version__ < '0.6':
                no_map = True
                log.debug('python-osmgpsmap < 0.6 detected')
        except:
            no_map = True
            log.debug('python-osmgpsmap not detected')

        log.debug('python-osmgpsmap > 0.5 detected')
        if not no_map and not self.is_active:
            from layers import DummyLayer

            vbox = self.xml.get_object('vbox1')
            vbox.set_size_request(400, -1)

            self.osm = osmgpsmap.GpsMap()
            self.osm.layer_add(osmgpsmap.GpsMapOsd(show_dpad=True,
                show_zoom=True))
            self.osm.layer_add(DummyLayer())
            lat = float(self.plugin.config['lat'])
            lon = float(self.plugin.config['lon'])
            self.osm.set_center_and_zoom(lat, lon, 12)
            self.path_to_image = os.path.abspath(gtkgui_helpers.get_icon_path(
                'gajim', 16))
            self.icon = gtk.gdk.pixbuf_new_from_file_at_size(
                self.path_to_image, 16, 16)
            self.osm.connect('button_release_event', self.map_clicked)
            vbox.pack_start(self.osm, expand=True, fill=True, padding=6)
            label = gtk.Label(_(
                'Click the right mouse button to specify the location, \n'\
                'middle mouse button to show / hide the contacts on the map'))
            vbox.pack_start(label, expand=False, fill=False, padding=6)
            self.is_active = True
            self.images = []
            self.osm_image = self.osm.image_add(lat, lon, self.icon)
            self.xml.get_object('lat').connect('changed', self.on_lon_changed)
            self.xml.get_object('lon').connect('changed', self.on_lon_changed)

    def on_hide(self, widget):
        for name in self.plugin.config_default_values:
            if name == 'presets':
                continue
            widget = self.xml.get_object(name)
            self.plugin.config[name] = widget.get_text()
            if self.plugin.active:
                self.plugin.activate()

    def map_clicked(self, osm, event):
        lat, lon = self.osm.get_event_location(event).get_degrees()
        if event.button == 3:
            self.osm.image_remove(self.osm_image)
            self.osm_image = self.osm.image_add(lat, lon, self.icon)
            self.xml.get_object('lat').set_text(str(lat))
            self.xml.get_object('lon').set_text(str(lon))
        if event.button == 2:
            self.show_contacts()

    def on_lon_changed(self, widget):
        try:
            lat = float(self.xml.get_object('lat').get_text())
            lon = float(self.xml.get_object('lon').get_text())
        except ValueError, e:
            return
        if not -85 < lat < 85 or not -180 < lon < 180:
            return
        self.osm.image_remove(self.osm_image)
        self.osm_image = self.osm.image_add(lat, lon, self.icon)
        self.osm.set_center(lat, lon)

    def show_contacts(self):
        if not self.images:
            data = {}
            accounts = gajim.contacts._accounts
            for account in accounts:
                if not gajim.account_is_connected(account):
                    continue
                for contact in accounts[account].contacts._contacts:
                    pep = accounts[account].contacts._contacts[contact][0].pep
                    if 'location' not in pep:
                        continue
                    lat = pep['location']._pep_specific_data.get('lat', None)
                    lon = pep['location']._pep_specific_data.get('lon', None)
                    if not lat or not lon:
                        continue
                    data[contact] = (lat, lon)
            for jid in data:
                path = gtkgui_helpers.get_path_to_generic_or_avatar(None,
                        jid=jid, suffix='')
                icon = gtk.gdk.pixbuf_new_from_file_at_size(path, 24, 24)
                image = self.osm.image_add(float(data[jid][0]),
                    float(data[jid][1]), icon)
                self.images.append(image)
        else:
            for image in self.images:
                self.osm.image_remove(image)
            self.images = []

    def on_preset_button_clicked(self, widget):
        def on_ok(preset_name):
            if preset_name == '':
                return
            preset = {}
            for name in self.plugin.config_default_values:
                if name == 'presets':
                    continue
                widget = self.xml.get_object(name)
                preset[name] = widget.get_text()
            preset = {preset_name: preset}
            presets = dict(self.plugin.config['presets'].items() + \
                preset.items())
            if preset_name not in self.plugin.config['presets'].keys():
                iter_ = self.preset_liststore.append((preset_name,))
            self.plugin.config['presets'] = presets
        self.set_modal(False)
        InputDialog(_('Save as Preset'), _('Please type a name for this preset'),
            is_modal=True, ok_handler=on_ok)

    def on_preset_combobox_changed(self, widget):
        model = widget.get_model()
        active = widget.get_active()
        if active < 0:
            self.xml.get_object('del_preset').set_sensitive(False)
            return
        pres_name = model[active][0].decode('utf-8')
        for name in self.plugin.config['presets'][pres_name].keys():
            widget = self.xml.get_object(name)
            widget.set_text(str(self.plugin.config['presets'][pres_name][name]))

        self.xml.get_object('del_preset').set_sensitive(True)

    def on_del_preset_clicked(self, widget):
        active = self.preset_combo.get_active()
        active_iter = self.preset_combo.get_active_iter()
        name = self.preset_liststore[active][0].decode('utf-8')
        presets = self.plugin.config['presets']
        del presets[name]
        self.plugin.config['presets'] = presets
        self.preset_liststore.remove(active_iter)
