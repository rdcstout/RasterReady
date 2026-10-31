import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json

from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QApplication

from rasterready import update_ui
from rasterready.updates import MAX_RESPONSE, REPOSITORY


class Reply(QObject):
    readyRead = Signal()
    finished = Signal()

    def __init__(self, payload, error=False):
        super().__init__()
        self.payload = payload
        self.failed = error
        self.aborted = False

    def setReadBufferSize(self, size):
        self.limit = size

    def readAll(self):
        payload, self.payload = self.payload, b""
        return payload

    def error(self):
        return (
            QNetworkReply.NetworkError.UnknownNetworkError
            if self.failed
            else QNetworkReply.NetworkError.NoError
        )

    def abort(self):
        if not self.aborted:
            self.aborted = self.failed = True
            self.finished.emit()


class Network:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0
        self.error = False

    def get(self, request):
        self.calls += 1
        self.request = request
        self.reply = Reply(self.payload, self.error)
        return self.reply

    def complete(self):
        self.reply.readyRead.emit()
        if not self.reply.aborted:
            self.reply.finished.emit()


def checker(tmp_path, payload):
    app = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    network = Network(payload)
    obj = update_ui.UpdateChecker(settings, network=network)
    obj._app = app
    results = []
    obj.result.connect(lambda result, manual: results.append((result, manual)))
    return obj, network, results


def test_weekly_attempt_persists_restart_and_disabled_manual_works(tmp_path, monkeypatch):
    monkeypatch.setattr(update_ui.time, "time", lambda: 10000000)
    obj, net, results = checker(tmp_path, b"[]")
    obj.check_if_due()
    assert net.calls == 1
    obj.check_if_due()
    assert net.calls == 1
    assert obj.settings.value("updates/last_attempt") == 10000000
    net.complete()
    assert results == []
    obj.check_if_due()
    assert net.calls == 1
    obj.stop()
    # A separate settings object models an app restart.
    again, net2, results2 = checker(tmp_path, b"[]")
    again.check_if_due()
    assert net2.calls == 0
    again.settings.setValue("updates/automatic", False)
    again.check(manual=True)
    net2.complete()
    assert results2[0][0].status == "unpublished" and results2[0][1]
    again.stop()


def test_failure_silent_automatically_but_clear_for_manual(tmp_path):
    obj, net, results = checker(tmp_path, b"not json")
    obj.check(manual=False)
    net.complete()
    assert not results
    obj.check(manual=True)
    net.complete()
    assert results[0][0].status == "unknown"
    net.error = True
    obj.check(manual=True)
    net.complete()
    assert results[-1][0].status == "unknown"
    obj.stop()


def test_oversized_reply_aborts_and_shutdown_prevents_new_checks(tmp_path):
    obj, net, results = checker(tmp_path, b"x" * (MAX_RESPONSE + 1))
    obj.check()
    net.complete()
    assert net.reply.aborted and obj.reply is None
    assert results[0][0].status == "unknown"
    obj.check()
    obj.stop()
    assert obj.reply is None
    count = net.calls
    obj.check_if_due()
    obj.check()
    assert net.calls == count


def test_dismissal_deduplicated_but_manual_reveals_update(tmp_path, monkeypatch):
    monkeypatch.setattr(update_ui, "target_platform", lambda: ("macos-arm64", ("dmg",)))
    tag = "v99.0"
    name = "RasterReady-99.0-macos-arm64.dmg"
    payload = json.dumps(
        [
            dict(
                tag_name=tag,
                draft=False,
                prerelease=False,
                html_url=f"{REPOSITORY}/releases/tag/{tag}",
                assets=[
                    dict(
                        name=name,
                        state="uploaded",
                        browser_download_url=f"{REPOSITORY}/releases/download/{tag}/{name}",
                    )
                ],
            )
        ]
    ).encode()
    obj, net, results = checker(tmp_path, payload)
    obj.check(False)
    net.complete()
    assert len(results) == 1
    obj.settings.setValue("updates/dismissed", "99.0")
    obj.check(False)
    net.complete()
    assert len(results) == 1
    obj.check(True)
    net.complete()
    assert len(results) == 2 and results[-1][1]
    obj.stop()
