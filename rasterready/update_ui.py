"""Nonblocking, bounded release requests and persistent weekly scheduling."""

import json
import time

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from . import __version__
from .updates import API_URL, MAX_RESPONSE, Update, automatic_due, select_release, target_platform


class UpdateChecker(QObject):
    result = Signal(object, bool)
    busy = Signal(bool)

    def __init__(self, settings, parent=None, network=None):
        super().__init__(parent)
        self.settings = settings
        self.network = QNetworkAccessManager(self) if network is None else network
        self.reply = None
        self.stopped = False
        self.timer = QTimer(self)
        self.timer.setInterval(60 * 60 * 1000)
        self.timer.timeout.connect(self.check_if_due)
        self.timer.start()
        QTimer.singleShot(1000, self.check_if_due)

    def enabled(self):
        return self.settings.value("updates/automatic", True, type=bool)

    def check_if_due(self):
        if not self.stopped and automatic_due(
            self.enabled(), self.settings.value("updates/last_attempt"), time.time()
        ):
            self.check(manual=False)

    def check(self, manual=True):
        if self.stopped or self.reply is not None:
            return
        if not manual:
            self.settings.setValue("updates/last_attempt", time.time())
            self.settings.sync()
        request = QNetworkRequest(QUrl(API_URL))
        request.setTransferTimeout(6000)
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(b"User-Agent", f"RasterReady/{__version__}".encode("ascii"))
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.SameOriginRedirectPolicy,
        )
        self.data = bytearray()
        self.manual = manual
        self.reply = self.network.get(request)
        self.reply.setReadBufferSize(MAX_RESPONSE + 1)
        self.reply.readyRead.connect(self.read)
        self.reply.finished.connect(self.finish)
        self.deadline = QTimer(self.reply)
        self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(self.reply.abort)
        self.deadline.start(8000)
        self.busy.emit(True)

    def read(self):
        self.data.extend(bytes(self.reply.readAll()))
        if len(self.data) > MAX_RESPONSE:
            self.reply.abort()

    def finish(self):
        self.read()
        reply, manual = self.reply, self.manual
        self.deadline.stop()
        result = Update("unknown")
        if reply.error() == QNetworkReply.NetworkError.NoError and len(self.data) <= MAX_RESPONSE:
            try:
                result = select_release(json.loads(self.data), __version__, target_platform())
            except (ValueError, UnicodeError, RecursionError):
                pass
        self.reply = None
        reply.deleteLater()
        self.busy.emit(False)
        if manual or (
            result.status == "newer" and result.version != self.settings.value("updates/dismissed")
        ):
            self.result.emit(result, manual)

    def stop(self):
        self.stopped = True
        self.timer.stop()
        if self.reply is not None:
            self.reply.abort()
