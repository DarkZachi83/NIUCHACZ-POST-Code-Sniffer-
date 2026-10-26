# NIUCHACZ firmware – zapis sesji na LittleFS
#
# Każda sesja (od zbocza RESET) to plik /sessions/NNNN.jsonl z liniami
# protokołu (ramki, diody). Dzięki temu PC może pobrać przebieg po fakcie.

import os

import config

BUF_MAX = 250      # linii w RAM, zanim zapis na flash zostanie wymuszony


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


class SessionStore:
    """Linie sesji czekają w RAM; na flash trafiają dopiero w flush().

    Każda operacja na flashu (zapis, utworzenie pliku, kasowanie starych sesji) potrafi
    zablokować ESP32 na dziesiątki–setki ms (kasowanie bloku). W tym czasie nikt nie
    czyta zatrzasku, więc pętla główna woła flush() tylko wtedy, gdy płyta stoi na
    jednym kodzie (pomiar 26.10.2026: przerwa 132 ms w środku serii, zgubione 80, 90, 2E).
    """

    def __init__(self, directory=config.SESSION_DIR, max_sessions=config.MAX_SESSIONS):
        self.dir = directory
        self.max = max_sessions
        if not _exists(self.dir):
            os.mkdir(self.dir)
        ids = self.list_ids()
        self.current_id = ids[-1] if ids else 0
        self._file = None
        self._file_id = 0          # sesja, do której pliku piszemy
        self._buf = []             # (id sesji, linia) – jeszcze nie na flashu

    def _path(self, sid):
        return "%s/%04d.jsonl" % (self.dir, sid)

    def list_ids(self):
        ids = []
        for name in os.listdir(self.dir):
            if name.endswith(".jsonl"):
                try:
                    ids.append(int(name[:-6]))
                except ValueError:
                    pass
        for sid, _ in getattr(self, "_buf", ()):    # sesje jeszcze tylko w RAM
            if sid not in ids:
                ids.append(sid)
        ids.sort()
        return ids

    def start(self):
        """Nowa sesja – bez dotykania flasha (plik powstanie przy flush)."""
        self.current_id += 1
        return self.current_id

    def append(self, line):
        if self.current_id == 0:
            return
        self._buf.append((self.current_id, line))
        if len(self._buf) >= BUF_MAX:
            self.flush()           # awaryjnie: RAM ESP32 jest mały

    def flush(self):
        if not self._buf:
            return
        for sid, line in self._buf:
            if sid != self._file_id:
                self._open(sid)
            self._file.write(line)
            self._file.write("\n")
        self._buf = []
        self._file.flush()

    def _open(self, sid):
        if self._file is not None:
            self._file.close()
        self._file = open(self._path(sid), "a")
        self._file_id = sid
        self._prune()

    def close(self):
        self.flush()
        if self._file is not None:
            self._file.close()
            self._file = None
            self._file_id = 0

    def read_lines(self, sid):
        self.flush()
        path = self._path(sid)
        if not _exists(path):
            return
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    yield line

    def clear(self):
        self._buf = []
        if self._file is not None:
            self._file.close()
            self._file = None
            self._file_id = 0
        for sid in self.list_ids():
            if _exists(self._path(sid)):
                os.remove(self._path(sid))
        self.current_id = 0

    def _prune(self):
        ids = [i for i in self.list_ids() if _exists(self._path(i))]
        while len(ids) > self.max:
            os.remove(self._path(ids.pop(0)))
