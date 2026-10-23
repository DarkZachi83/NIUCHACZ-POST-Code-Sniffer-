# NIUCHACZ firmware – ten sam protokół przez USB (port szeregowy REPL).
# Do debugowania przy podłączonym kablu. Odczyt komend nieblokujący (select.poll).

import sys
import select


class UsbLink:
    def __init__(self, on_command, enabled=True):
        self.on_command = on_command
        self.enabled = enabled
        self._poll = select.poll()
        self._poll.register(sys.stdin, select.POLLIN)
        self._buf = ""

    def send(self, text):
        if self.enabled:
            sys.stdout.write(text + "\n")

    def poll(self):
        """Wołane okresowo z pętli głównej."""
        if not self.enabled:
            return
        while self._poll.poll(0):
            ch = sys.stdin.read(1)
            if not ch:
                break
            if ch in "\r\n":
                text, self._buf = self._buf.strip(), ""
                if text:
                    self.on_command(text, self.send)
            else:
                self._buf += ch
                if len(self._buf) > 256:
                    self._buf = ""
