import logging

import PyATEMMax
from PyATEMMax.ATEMProtocolEnums import ATEMTransitionStyles, ATEMVideoModeFormats

VIDEO_FORMATS = {f[1:] for f in dir(ATEMVideoModeFormats) if f.startswith("f")}


class PyATEMSwitcher:
    def __init__(self, config):
        self.atem = PyATEMMax.ATEMMax()
        self.config = config.get("atem", {})
        self.log = logging.getLogger("Switcher")

        self._connect_subscribers = []
        self._connect_attempt_subscribers = []
        self._disconnect_subscribers = []
        self._receive_subscribers = []

        self._validate_config()

        self.atem.registerEvent(
            self.atem.atem.events.connect,
            self._on_connect,
        )
        self.atem.registerEvent(
            self.atem.atem.events.connectAttempt,
            self._on_connect_attempt,
        )
        self.atem.registerEvent(
            self.atem.atem.events.disconnect,
            self._on_disconnect,
        )
        self.atem.registerEvent(
            self.atem.atem.events.receive,
            self._on_receive,
        )

    def _on_connect(self, params):
        self.log.debug(f"_on_connect({repr(params)})")
        self._push_config()
        for callback in self._connect_subscribers:
            callback(params)

    def _on_connect_attempt(self, params):
        self.log.debug(f"_on_connect_attempt({repr(params)})")
        for callback in self._connect_attempt_subscribers:
            callback(params)

    def _on_disconnect(self, params):
        self.log.debug(f"_on_disconnect({repr(params)})")
        for callback in self._disconnect_subscribers:
            callback(params)

    def _on_receive(self, params):
        self.log.debug(f"_on_receive({repr(params)})")
        for callback in self._receive_subscribers:
            callback(params)

    def _push_config(self):
        conf = self.config.get("settings", {})
        # TODO media upload to MP1

        if "video_mode" in self.config:
            video_mode = getattr(
                ATEMVideoModeFormats,
                "f" + self.config["video_mode"],
            )
            if self.atem.videoMode.format != video_mode:
                self.atem.setVideoModeFormat(video_mode)

        if conf.get("inputs", None):
            for key, name in conf["inputs"].items():
                try:
                    input_number = getattr(self.atem.atem.videoSources, key)
                    long_name = self.atem.inputProperties[input_number].longName
                    if name == long_name:
                        continue
                    self.log.debug(f"setting input {input_number} to name '{name}'")
                    self.atem.setInputLongName(input_number, name)
                    self.atem.setInputShortName(input_number, name[0:4].upper())
                except Exception as e:
                    self.log.error(
                        "An error occurred while trying to adjust input names"
                    )
                    self.log.exception(e)

    def _validate_config(self):
        if "ip" not in self.config:
            raise KeyError("Please set ATEM IP in config!")
        if (
            "video_mode" in self.config
            and self.config["video_mode"] not in VIDEO_FORMATS
        ):
            raise ValueError(
                f'ATEM video_mode {self.config["video_mode"]} '
                "is not a valid video mode, must be one of: "
                f'{", ".join(sorted(VIDEO_FORMATS))}'
            )

    def connect(self):
        self.log.info("Initiating connection to switcher")
        self.atem.connect(self.config["ip"])

    def disconnect(self):
        self.atem.disconnect()

    def on_connect(self, callback):
        self._connect_subscribers.append(callback)

    def on_connect_attempt(self, callback):
        self._connect_attempt_subscribers.append(callback)

    def on_disconnect(self, callback):
        self._disconnect_subscribers.append(callback)

    def on_receive(self, callback):
        self._receive_subscribers.append(callback)

    def trans(self, input):
        self.log.debug(f"hehehehe trans({repr(input)})")
        self.atem.setPreviewInputVideoSource(
            ATEMTransitionStyles.mix,
            input,
        )
        self.atem.setTransitionMixRate(0, 10)
        self.atem.execAutoME(0)
