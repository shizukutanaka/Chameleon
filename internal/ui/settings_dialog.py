import os
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QFileDialog, QHBoxLayout
import sounddevice as sd

VOICE_MODELS_DIR = os.path.join(os.path.dirname(__file__), '../../voice_models')

class SettingsDialog(QDialog):
    def __init__(self, parent=None, current_device=None, current_dir=None, current_model=None):
        super().__init__(parent)
        self.setWindowTitle('設定')
        self.selected_device = current_device
        self.selected_dir = current_dir
        self.selected_model = current_model
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # 録音デバイス選択
        layout.addWidget(QLabel('録音デバイス:'))
        self.device_combo = QComboBox()
        devices = [d['name'] for d in sd.query_devices() if d['max_input_channels'] > 0]
        self.device_combo.addItems(devices)
        if self.selected_device in devices:
            self.device_combo.setCurrentText(self.selected_device)
        layout.addWidget(self.device_combo)

        # 保存先ディレクトリ
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel('保存先:'))
        self.dir_label = QLabel(self.selected_dir or '')
        dir_layout.addWidget(self.dir_label)
        dir_btn = QPushButton('参照...')
        dir_btn.clicked.connect(self.select_dir)
        dir_layout.addWidget(dir_btn)
        layout.addLayout(dir_layout)

        # 既定モデル
        layout.addWidget(QLabel('既定モデル:'))
        self.model_combo = QComboBox()
        models = [d for d in os.listdir(VOICE_MODELS_DIR) if os.path.isdir(os.path.join(VOICE_MODELS_DIR, d))]
        self.model_combo.addItems(models)
        if self.selected_model in models:
            self.model_combo.setCurrentText(self.selected_model)
        layout.addWidget(self.model_combo)

        # OK/Cancel
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton('OK')
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton('キャンセル')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def select_dir(self):
        d = QFileDialog.getExistingDirectory(self, '保存先ディレクトリ選択')
        if d:
            self.dir_label.setText(d)

    def get_settings(self):
        return {
            'device': self.device_combo.currentText(),
            'dir': self.dir_label.text(),
            'model': self.model_combo.currentText()
        }
