# NIUCHACZ firmware – zapis sesji na LittleFS
#
# Każda sesja (od zbocza RESET) to plik /sessions/NNNN.jsonl z liniami
# protokołu (ramki, diody). Dzięki temu PC może pobrać przebieg po fakcie.

import os

import config


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


class SessionStore:
    def __init__(self, directory=config.SESSION_DIR, max_sessions=config.MAX_SESSIONS):
        self.dir = directory
        self.max = max_sessions
        if not _exists(self.dir):
            os.mkdir(self.dir)
        ids = self.list_ids()
        self.current_id = ids[-1] if ids else 0
        self._file = None
        self._pending = 0

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
        ids.sort()
        return ids

    def start(self):
        self.close()
        self.current_id += 1
        self._file = open(self._path(self.current_id), "w")
        self._prune()
        return self.current_id

    def append(self, line):
        if self._file is None:
            return
        self._file.write(line)
        self._file.write("\n")
        self._pending += 1
        if self._pending >= 200:
            # awaryjnie; normalnie flush robi pętla główna, gdy płyta stoi (zapis na flash
            # blokuje ESP32 na dziesiątki ms – w trakcie serii kodów gubilibyśmy kody)
            self.flush()

    def flush(self):
        if self._file is not None and self._pending:
            self._file.flush()
            self._pending = 0

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None
            self._pending = 0

    def read_lines(self, sid):
        if sid == self.current_id:
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
        self.close()
        for sid in self.list_ids():
            os.remove(self._path(sid))
        self.current_id = 0

    def _prune(self):
        ids = self.list_ids()
        while len(ids) > self.max:
            os.remove(self._path(ids.pop(0)))
