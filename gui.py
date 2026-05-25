import gi

gi.require_version("Gtk", "3.0")
import logging
from threading import Lock

from gi.repository import Gdk, GObject, Gtk

BUTTON_SPACING = 5


class PyATEMSwitcherGui:
    def __init__(self, config, switcher):
        self.log = logging.getLogger("GUI")
        self.config = config

        cssProvider = Gtk.CssProvider()
        cssProvider.load_from_path("style.css")
        screen = Gdk.Screen.get_default()
        styleContext = Gtk.StyleContext()
        styleContext.add_provider_for_screen(
            screen,
            cssProvider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER,
        )

        self.window = Gtk.Window()
        self.window.connect("destroy", self._exit)

        self.window.set_wmclass("pygtk-atem-switcher", "PyGTK-ATEM-Switcher")

        self.switcher = switcher
        self.switcher.on_connect(self._switcher_connected)
        self.switcher.on_connect_attempt(self._switcher_connect_attempt)
        self.switcher.on_disconnect(self._switcher_disconnected)

        self.switcher.on_connect(self._switcher_state_changed)
        self.switcher.on_receive(self._switcher_state_changed)

        self.window.set_border_width(BUTTON_SPACING)

        self.header = Gtk.HeaderBar()
        self.header.props.title = "PyATEMSwitcherGui: Idle"
        self.window.set_titlebar(self.header)

        self.redraw_lock = Lock()
        self.box = None
        self.buttons = {}

    def _exit(self, *args, **kwargs):
        self.switcher.disconnect()
        Gtk.main_quit(*args, **kwargs)

    def _button_clicked(self, button, name):
        self.log.info(f"Button {name} was pressed")
        with self.redraw_lock:
            for btn in self.buttons:
                ctx = self.buttons[btn][0].get_style_context()
                if btn == name:
                    self.log.debug(f'{btn}.add_class("selected")')
                    ctx.add_class("selected")
                    self.switcher.trans(self.buttons[btn][1])
                else:
                    self.log.debug(f'{btn}.remove_class("selected")')
                    ctx.remove_class("selected")

    def _switcher_connected(self, params):
        switcher = params["switcher"]
        log = logging.getLogger("GUI connected")

        log.debug(f"_switcher_connected({params})")
        log.info(f'Connected to "{switcher.atemModel}" @ {switcher.ip}')
        self.header.props.title = f"{switcher.atemModel} @ {switcher.ip}"

        with self.redraw_lock:
            if self.box is not None:
                log.debug("Removing old VBox from window")
                self.window.remove(self.box)
            self.window.show_all()
            self.box = None
            self.buttons = {}
            log.debug("Button state cleared, creating buttons")


            possibleInputs = {}
            for _, value in enumerate(switcher.atem.videoSources):
                if value.name.endswith("Direct") or value.name.endswith("Prev") or value.name.endswith("Prog") or value.name.endswith("Key"):
                    continue
                possibleInputs[value.name] = switcher.inputProperties[value.name]

            inputs = {}
            for idx, i in possibleInputs.items():
                if not i.shortName:
                    continue
                if i.shortName.lower() in ("-", "empty", "x"):
                    continue
                if f"in_{i.shortName}" in self.buttons:
                    log.warning(f"ignoring duplicate button {i.shortName}")
                    log.debug(self.buttons)
                    continue
                log.debug(
                    f"Creating Button for {i.shortName} of type {i.externalPortType}: {i.longName}"
                )
                btn = Gtk.Button.new_with_label(i.longName)
                btn.connect(
                    "clicked",
                    self._button_clicked,
                    f"in_{i.shortName}",
                )
                log.debug(f"Adding {i.shortName} to FlowBox")
                self.buttons[f"in_{i.shortName}"] = (btn, idx)
                inputs.setdefault(str(i.externalPortType), []).append(btn)

            log.debug("Creating vertically stacked box as container")
            self.box = Gtk.VBox(spacing=BUTTON_SPACING)

            for input_type in ("hdmi", "sdi", "internal"):
                if input_type not in inputs:
                    continue

                for btn in inputs[input_type]:
                    self.box.pack_start(btn, True, True, 0)

            log.debug("All buttons added, adding box to window")
            self.window.add(self.box)
            self.window.show_all()
            self.log.debug("done")

    def _switcher_connect_attempt(self, params):
        self.header.props.title = "PyATEMSwitcherGui: Connecting ..."

    def _switcher_disconnected(self, params):
        with self.redraw_lock:
            if self.box is not None:
                self.window.remove(self.box)
            self.box = None
            self.buttons = {}
            self.window.show_all()
        self.header.props.title = "PyATEMSwitcherGui: Not connected"

    def _switcher_state_changed(self, params):
        cmd = params.get("cmd", "PrgI")

        if cmd in ("PrgI", "PrvI"):
            pgm = params["switcher"].programInput[0].videoSource
            prv = params["switcher"].previewInput[0].videoSource
            pgm_n = params["switcher"].inputProperties[pgm].shortName
            prv_n = params["switcher"].inputProperties[prv].shortName
            for btn in self.buttons:
                ctx = self.buttons[btn][0].get_style_context()
                if btn == f"in_{pgm_n}":
                    ctx.add_class("program")
                else:
                    ctx.remove_class("program")
                if btn == f"in_{prv_n}" and pgm != prv:
                    ctx.add_class("preview")
                else:
                    ctx.remove_class("preview")
                ctx.remove_class("selected")
        elif cmd == "TrPs" and params["switcher"].transition[0].position == 0:
            for btn in self.buttons:
                ctx = self.buttons[btn][0].get_style_context()
                ctx.remove_class("preview")
        elif cmd == "InPr":
            for idx, i in enumerate(params["switcher"].inputProperties):
                if not i.shortName:
                    break
                if (
                    f"in_{i.shortName}" not in self.buttons
                    or i.shortName.lower() in ("-", "empty", "x")
                    or self.buttons[f"in_{i.shortName}"][1] != idx
                ):
                    self.log.warning(
                        f"amount of buttons changed, re-drawing the window"
                    )
                    self._switcher_connected(params)
                elif self.buttons[f"in_{i.shortName}"][0].get_label() != str(
                    i.longName
                ):
                    with self.redraw_lock:
                        self.log.info(
                            f"setting label for button {i.shortName} to: {i.longName}"
                        )
                        self.buttons[f"in_{i.shortName}"][0].set_label(str(i.longName))

    def main_loop(self):
        self.switcher.connect()
        self.window.show_all()
        Gtk.main()
