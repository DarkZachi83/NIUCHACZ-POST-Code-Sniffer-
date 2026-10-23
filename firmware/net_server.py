# NIUCHACZ firmware – serwer TCP (Wi-Fi). Rozsyła linie do wszystkich klientów
# i przekazuje odebrane komendy do obsługi.

import asyncio

import config


class NetServer:
    def __init__(self, on_command):
        self.on_command = on_command   # funkcja(text, reply_fn)
        self.clients = []

    async def start(self):
        await asyncio.start_server(self._client, "0.0.0.0", config.TCP_PORT)

    async def _client(self, reader, writer):
        self.clients.append(writer)
        try:
            from protocol import hello
            writer.write((hello() + "\n").encode())
            await writer.drain()
            while True:
                raw = await reader.readline()
                if not raw:
                    break
                text = raw.decode().strip()
                if text:
                    self.on_command(text, lambda s, w=writer: self._send_to(w, s))
        except OSError:
            pass
        finally:
            if writer in self.clients:
                self.clients.remove(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except OSError:
                pass

    def _send_to(self, writer, text):
        try:
            writer.write((text + "\n").encode())
        except OSError:
            if writer in self.clients:
                self.clients.remove(writer)

    def broadcast(self, text):
        data = (text + "\n").encode()
        for w in list(self.clients):
            try:
                w.write(data)
            except OSError:
                self.clients.remove(w)

    async def drain(self):
        for w in list(self.clients):
            try:
                await w.drain()
            except OSError:
                if w in self.clients:
                    self.clients.remove(w)
