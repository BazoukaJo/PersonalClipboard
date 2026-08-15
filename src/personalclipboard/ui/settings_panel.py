"""Modal settings: language, opacity, models, VAD, type-ahead."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from personalclipboard.config import (
    OLLAMA_CHOICES,
    OPACITY_DEFAULT,
    OPACITY_MAX,
    OPACITY_MIN,
    WHISPER_CHOICES,
)
from personalclipboard.ui.i18n import LANGS, t
from personalclipboard.ui.theme import control_chrome, pointing

_ROW_H = 50
_CONTROL_H = 36
_LABEL_W = 100


class SettingsPanel(QDialog):
    language_changed = pyqtSignal(str)
    opacity_changed = pyqtSignal(int)
    whisper_changed = pyqtSignal(str)
    ollama_changed = pyqtSignal(str)
    vad_changed = pyqtSignal(bool)
    predict_changed = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsDialog")
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumSize(460, 420)
        self.resize(520, 480)
        self.setStyleSheet(
            "QDialog { background: #1a1a1c; color: #f0f0f2; }" + control_chrome()
        )
        self._lang = "en"
        self._updating = False
        self._make_fields()
        self._style_fields()
        self._body = QWidget()
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(4, 8, 4, 8)
        body_layout.setSpacing(12)
        body_layout.addWidget(_field_row(self._lang_label, self._lang_box))
        body_layout.addWidget(
            _slider_row(self._opacity_label, self._opacity, self._opacity_value)
        )
        body_layout.addWidget(_field_row(self._whisper_label, self._whisper))
        body_layout.addWidget(_field_row(self._ollama_label, self._ollama))
        body_layout.addWidget(_box_row(self._vad))
        body_layout.addWidget(_box_row(self._predict))
        body_layout.addStretch(1)
        self._scroll = QScrollArea()
        self._scroll.setObjectName("settingsScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setWidget(self._body)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)
        root.addLayout(self._make_header())
        root.addWidget(self._scroll, 1)
        self.retranslate("en")

    def _make_header(self) -> QHBoxLayout:
        pointing(self._close)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self._header)
        row.addStretch(1)
        row.addWidget(self._close)
        return row

    def _make_fields(self) -> None:
        self._header = QLabel()
        self._header.setObjectName("brand")
        self._close = QPushButton()
        self._close.setObjectName("ghost")
        self._close.clicked.connect(self.accept)
        self._lang_label = QLabel()
        self._lang_label.setObjectName("fieldLabel")
        self._lang_box = QComboBox()
        for code, name in LANGS:
            self._lang_box.addItem(name, code)
        self._lang_box.currentIndexChanged.connect(self._emit_language)
        self._opacity_label = QLabel()
        self._opacity_label.setObjectName("fieldLabel")
        self._opacity = QSlider(Qt.Orientation.Horizontal)
        self._opacity.setRange(OPACITY_MIN, OPACITY_MAX)
        self._opacity.setValue(OPACITY_DEFAULT)
        self._opacity.setToolTip("How solid the overlay is. 100% is fully opaque.")
        self._opacity.valueChanged.connect(self._on_opacity_moved)
        self._opacity_value = QLabel(f"{OPACITY_DEFAULT}%")
        self._opacity_value.setObjectName("opacityValue")
        self._opacity_value.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._whisper_label = QLabel()
        self._whisper_label.setObjectName("fieldLabel")
        self._whisper = QComboBox()
        for name in WHISPER_CHOICES:
            self._whisper.addItem(name)
        self._whisper.currentTextChanged.connect(self._emit_whisper)
        self._ollama_label = QLabel()
        self._ollama_label.setObjectName("fieldLabel")
        self._ollama = QComboBox()
        self._ollama.setEditable(True)
        for name in OLLAMA_CHOICES:
            self._ollama.addItem(name)
        self._ollama.currentTextChanged.connect(self._emit_ollama)
        self._vad = QCheckBox()
        pointing(self._vad)
        self._vad.toggled.connect(self._emit_vad)
        self._predict = QCheckBox()
        pointing(self._predict)
        self._predict.toggled.connect(self._emit_predict)

    def _style_fields(self) -> None:
        font = QFont("Segoe UI", 11)
        for box in (self._lang_box, self._whisper, self._ollama):
            box.setObjectName("settingField")
            box.setFont(font)
            box.setFixedHeight(_CONTROL_H)
            box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._opacity.setObjectName("settingField")
        self._opacity.setFixedHeight(_CONTROL_H)
        for box in (self._vad, self._predict):
            box.setObjectName("settingField")
            box.setFont(font)
            box.setFixedHeight(_CONTROL_H)
        self.setFont(QFont("Segoe UI", 10))

    def retranslate(self, lang: str) -> None:
        self._lang = lang
        self.setWindowTitle(t(lang, "settings"))
        self._header.setText(t(lang, "settings"))
        self._header.setToolTip(t(lang, "settings_tip"))
        self._close.setText(t(lang, "close"))
        self._close.setToolTip(t(lang, "close_tip"))
        self._lang_label.setText(t(lang, "language"))
        self._lang_label.setToolTip(t(lang, "language_tip"))
        self._lang_box.setToolTip(t(lang, "language_tip"))
        self._opacity_label.setText(t(lang, "opacity"))
        self._opacity.setToolTip(t(lang, "opacity_tip"))
        self._whisper_label.setText(t(lang, "whisper"))
        self._whisper.setToolTip(t(lang, "whisper_tip"))
        self._ollama_label.setText(t(lang, "corrector"))
        self._ollama.setToolTip(t(lang, "corrector_tip"))
        self._vad.setText(t(lang, "vad"))
        self._vad.setToolTip(t(lang, "vad_tip"))
        self._predict.setText(t(lang, "predict"))
        self._predict.setToolTip(t(lang, "predict_tip"))

    def set_values(
        self,
        *,
        language: str,
        opacity: int,
        whisper: str,
        ollama: str,
        ollama_models: list[str],
        vad: bool,
        predict: bool,
    ) -> None:
        self._updating = True
        index = self._lang_box.findData(language)
        self._lang_box.setCurrentIndex(index if index >= 0 else 0)
        self._opacity.setValue(opacity)
        self._opacity_value.setText(f"{self._opacity.value()}%")
        self._fill_combo(self._whisper, list(WHISPER_CHOICES), whisper)
        models = list(dict.fromkeys(list(OLLAMA_CHOICES) + ollama_models + [ollama]))
        self._fill_combo(self._ollama, models, ollama)
        self._vad.setChecked(vad)
        self._predict.setChecked(predict)
        self._updating = False

    def _fill_combo(self, box: QComboBox, names: list[str], current: str) -> None:
        box.blockSignals(True)
        box.clear()
        for name in names:
            if name:
                box.addItem(name)
        found = box.findText(current)
        if found >= 0:
            box.setCurrentIndex(found)
        elif current:
            box.addItem(current)
            box.setCurrentText(current)
        box.blockSignals(False)

    def _emit_language(self) -> None:
        if not self._updating:
            code = self._lang_box.currentData()
            if isinstance(code, str):
                self.language_changed.emit(code)

    def _on_opacity_moved(self, value: int) -> None:
        self._opacity_value.setText(f"{value}%")
        self._emit_opacity(value)

    def _emit_opacity(self, value: int) -> None:
        if not self._updating:
            self.opacity_changed.emit(value)

    def _emit_whisper(self, value: str) -> None:
        if not self._updating and value.strip():
            self.whisper_changed.emit(value.strip())

    def _emit_ollama(self, value: str) -> None:
        if not self._updating and value.strip():
            self.ollama_changed.emit(value.strip())

    def _emit_vad(self, checked: bool) -> None:
        if not self._updating:
            self.vad_changed.emit(checked)

    def _emit_predict(self, checked: bool) -> None:
        if not self._updating:
            self.predict_changed.emit(checked)


def _field_row(label: QLabel, widget: QWidget) -> QWidget:
    row = QWidget()
    row.setFixedHeight(_ROW_H)
    row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 3, 0, 3)
    layout.setSpacing(12)
    label.setFixedWidth(_LABEL_W)
    label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    font = QFont("Segoe UI", 11)
    label.setFont(font)
    layout.addWidget(label)
    layout.addWidget(widget, 1)
    return row


def _slider_row(label: QLabel, slider: QSlider, value: QLabel) -> QWidget:
    row = QWidget()
    row.setFixedHeight(_ROW_H)
    row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 3, 0, 3)
    layout.setSpacing(12)
    label.setFixedWidth(_LABEL_W)
    label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    font = QFont("Segoe UI", 11)
    label.setFont(font)
    value.setFixedWidth(44)
    pointing(slider)
    layout.addWidget(label)
    layout.addWidget(slider, 1)
    layout.addWidget(value)
    return row


def _box_row(widget: QWidget) -> QWidget:
    row = QWidget()
    row.setFixedHeight(_ROW_H)
    row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 3, 0, 3)
    layout.addWidget(widget)
    return row
