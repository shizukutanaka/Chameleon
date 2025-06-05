import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QComboBox, QVBoxLayout, QFileDialog, QMessageBox, QProgressBar, QListWidget, QListWidgetItem, QHBoxLayout
)
from waveform_utils import WaveformCanvas
from specgram_utils import SpecgramCanvas
from PyQt5.QtCore import Qt
import subprocess

VOICE_MODELS_DIR = os.path.join(os.path.dirname(__file__), '../../voice_models')
AUDIO_TMP = os.path.join(os.path.dirname(__file__), '../../tmp/gui_input.wav')
CHANGED_TMP = os.path.join(os.path.dirname(__file__), '../../tmp/gui_changed.wav')

import json
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '../../config_ui.json')

class VoiceChangerGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Chameleon ボイスチェンジャー')
        self.setGeometry(200, 200, 400, 250)
        self.setAcceptDrops(True)
        self.favorite_models = set()
        self.history = []
        self.settings = {
            'device': None,
            'dir': None,
            'model': None
        }
        self.load_config()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        self.status_label = QLabel('音声ファイルを選択 or 録音してください')
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setMaximum(100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.waveform_canvas = None

        self.model_combo = QComboBox()
        self.model_combo.addItems(self.get_voice_models())
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel('変換先の声モデル:'))
        model_layout.addWidget(self.model_combo)
        from PyQt5.QtGui import QIcon
        self.star_btn = QPushButton()
        self.star_btn.setIcon(QIcon.fromTheme('emblem-favorite'))
        self.star_btn.setText('★')
        self.star_btn.setToolTip('お気に入り登録/解除')
        self.star_btn.clicked.connect(self.toggle_favorite)
        model_layout.addWidget(self.star_btn)
        layout.addLayout(model_layout)
        self.reload_btn = QPushButton('モデル一覧リロード')
        self.reload_btn.setIcon(QIcon.fromTheme('view-refresh'))
        self.reload_btn.clicked.connect(self.reload_models)
        layout.addWidget(self.reload_btn)

        self.select_btn = QPushButton('音声ファイルを選択')
        self.select_btn.setIcon(QIcon.fromTheme('document-open'))
        self.select_btn.clicked.connect(self.select_file)
        layout.addWidget(self.select_btn)

        self.record_btn = QPushButton('マイク録音')
        self.record_btn.setIcon(QIcon.fromTheme('media-record'))
        self.record_btn.clicked.connect(self.record_audio)
        layout.addWidget(self.record_btn)

        self.convert_btn = QPushButton('変換＆再生')
        self.convert_btn.setIcon(QIcon.fromTheme('media-playback-start'))
        self.convert_btn.clicked.connect(self.convert_and_play)
        layout.addWidget(self.convert_btn)

        self.settings = {
            'device': None,
            'dir': None,
            'model': None
        }
        self.setLayout(layout)
        self.input_audio = None
        self.waveform_canvas = None
        self.specgram_canvas = None

        self.settings_btn = QPushButton('設定')
        self.settings_btn.setIcon(QIcon.fromTheme('preferences-system'))
        self.settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(self.settings_btn)

        layout.addWidget(QLabel('変換履歴:'))
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.on_history_clicked)
        layout.addWidget(self.history_list)
        # 履歴リスト復元
        for h in self.history:
            input_file, model, output_file, ts = h
            item = QListWidgetItem(f'{os.path.basename(input_file)} → {model} [{ts}]')
            item.setIcon(QIcon.fromTheme('media-playback-start'))
            self.history_list.addItem(item)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(url.toLocalFile().lower().endswith(('.wav', '.mp3', '.m4a', '.flac')) for url in urls):
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            fname = url.toLocalFile()
            if fname.lower().endswith(('.wav', '.mp3', '.m4a', '.flac')):
                self.input_audio = fname
                self.status_label.setText(f'D&D選択: {os.path.basename(fname)}')
                self.show_waveform(self.input_audio, title='入力音声 波形')
                break

    def reload_models(self):
        self.model_combo.clear()
        self.model_combo.addItems(self.get_voice_models())
        self.update_favorite_pins()
        self.status_label.setText('モデル一覧をリロードしました')

    def open_settings(self):
        from settings_dialog import SettingsDialog
        dlg = SettingsDialog(self, current_device=self.settings['device'], current_dir=self.settings['dir'], current_model=self.settings['model'])
        if dlg.exec_() == dlg.Accepted:
            self.settings = dlg.get_settings()
            self.status_label.setText('設定を更新しました')

    def get_voice_models(self):
        if not os.path.exists(VOICE_MODELS_DIR):
            return []
        # お気に入りは上部にピン留め
        all_models = [d for d in os.listdir(VOICE_MODELS_DIR) if os.path.isdir(os.path.join(VOICE_MODELS_DIR, d))]
        fav = [m for m in all_models if m in self.favorite_models]
        rest = [m for m in all_models if m not in self.favorite_models]
        return fav + rest

    def toggle_favorite(self):
        model = self.model_combo.currentText()
        if not model:
            return
        if model in self.favorite_models:
            self.favorite_models.remove(model)
        else:
            self.favorite_models.add(model)
        self.reload_models()

    def update_favorite_pins(self):
        # ドロップダウンの順序をお気に入り優先に
        current = self.model_combo.currentText()
        self.model_combo.clear()
        self.model_combo.addItems(self.get_voice_models())
        if current:
            self.model_combo.setCurrentText(current)

    def add_history(self, input_file, model, output_file):
        from datetime import datetime
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.history.append((input_file, model, output_file, ts))
        item = QListWidgetItem(f'{os.path.basename(input_file)} → {model} [{ts}]')
        self.history_list.addItem(item)

    def on_history_clicked(self, item):
        idx = self.history_list.row(item)
        if idx < 0 or idx >= len(self.history):
            return
        input_file, model, output_file, ts = self.history[idx]
        # 再生のみ（再変換も可）
        try:
            subprocess.run([
                sys.executable, os.path.join(os.path.dirname(__file__), '../audio/play_wav.py'),
                '--input', output_file
            ], check=True)
            self.status_label.setText(f'履歴再生: {os.path.basename(output_file)}')
        except Exception as e:
            self.show_error('履歴再生エラー', str(e))

    def select_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, '音声ファイルを選択', '', '音声ファイル (*.wav *.mp3 *.m4a *.flac)')
        if fname:
            self.input_audio = fname
            self.status_label.setText(f'選択中: {os.path.basename(fname)}')
            self.show_waveform(self.input_audio, title='入力音声 波形')

    def record_audio(self):
        # 録音はmic_record.pyを利用
        duration, ok = self.get_duration_dialog()
        if not ok:
            return
        try:
            subprocess.run([
                sys.executable, os.path.join(os.path.dirname(__file__), '../audio/mic_record.py'),
                '--output', AUDIO_TMP,
                '--duration', str(duration)
            ], check=True)
            self.input_audio = AUDIO_TMP
            self.status_label.setText(f'録音完了: {AUDIO_TMP}')
            self.show_waveform(self.input_audio, title='入力音声 波形')
        except Exception as e:
            self.show_error('録音エラー', str(e))

    def convert_and_play(self):
        if not self.input_audio or not os.path.exists(self.input_audio):
            self.show_error('エラー', '音声ファイルが選択または録音されていません')
            return
        model_name = self.model_combo.currentText()
        self.set_processing(True, '変換中...')
        try:
            subprocess.run([
                sys.executable, os.path.join(os.path.dirname(__file__), '../audio/voice_changer.py'),
                '--input', self.input_audio,
                '--target_voice', model_name,
                '--output', CHANGED_TMP
            ], check=True)
            self.progress.setValue(60)
            self.show_waveform(CHANGED_TMP, title='変換後 波形')
            self.show_specgram(CHANGED_TMP, title='変換後 スペクトル')
            # 再生
            self.set_processing(True, '再生中...')
            subprocess.run([
                sys.executable, os.path.join(os.path.dirname(__file__), '../audio/play_wav.py'),
                '--input', CHANGED_TMP
            ], check=True)
            self.status_label.setText('変換・再生完了')
            self.progress.setValue(100)
        except Exception as e:
            self.show_error('変換/再生エラー', str(e))
        finally:
            self.set_processing(False)

    def show_error(self, title, msg):
        faq_url = 'https://github.com/shizukutanaka/Chameleon/wiki/FAQ'
        support_url = 'https://github.com/shizukutanaka/Chameleon/issues'
        detail = f"{msg}\n\n【よくある質問】\n{faq_url}\n【サポート・バグ報告】\n{support_url}"
        QMessageBox.critical(self, title, detail)

    def get_duration_dialog(self):
        # シンプルな録音秒数入力（デフォルト5秒）
        from PyQt5.QtWidgets import QInputDialog
        sec, ok = QInputDialog.getInt(self, '録音秒数', '録音時間（秒）:', 5, 1, 60, 1)
        return sec, ok

    def show_waveform(self, audio_path, title=''):
        # 既存の波形キャンバスを消して新しく描画
        if self.waveform_canvas:
            self.layout().removeWidget(self.waveform_canvas)
            self.waveform_canvas.setParent(None)
            self.waveform_canvas = None
        try:
            self.waveform_canvas = WaveformCanvas(audio_path, self, width=4, height=1.5, title=title)
            self.layout().addWidget(self.waveform_canvas)
        except Exception as e:
            self.status_label.setText(f'波形表示エラー: {e}')

    def show_specgram(self, audio_path, title=''):
        # 既存のスペクトルキャンバスを消して新しく描画
        if self.specgram_canvas:
            self.layout().removeWidget(self.specgram_canvas)
            self.specgram_canvas.setParent(None)
            self.specgram_canvas = None
        try:
            self.specgram_canvas = SpecgramCanvas(audio_path, self, width=4, height=1.5, title=title)
            self.layout().addWidget(self.specgram_canvas)
        except Exception as e:
            self.status_label.setText(f'スペクトル表示エラー: {e}')

    def set_processing(self, processing, msg=None):
        # ボタン有効/無効化、進捗とメッセージ
        for btn in [self.select_btn, self.record_btn, self.convert_btn]:
            btn.setEnabled(not processing)
        self.progress.setVisible(processing)
        if processing:
            self.progress.setValue(20)
            if msg:
                self.status_label.setText(msg)
        else:
            self.progress.setValue(0)

    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                self.settings = cfg.get('settings', self.settings)
                self.favorite_models = set(cfg.get('favorite_models', []))
                self.history = cfg.get('history', [])
            except Exception:
                pass

    def save_config(self):
        cfg = {
            'settings': self.settings,
            'favorite_models': list(self.favorite_models),
            'history': self.history
        }
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

def apply_dark_theme(app):
    # シンプルなダークテーマ用スタイルシート
    app.setStyleSheet('''
        QWidget { background: #232629; color: #f0f0f0; font-size: 12pt; }
        QPushButton { background: #444; color: #fff; border-radius: 5px; min-height: 28px; }
        QPushButton:hover { background: #666; }
        QComboBox, QListWidget, QLineEdit, QLabel { background: #232629; color: #f0f0f0; }
        QProgressBar { background: #333; color: #fff; border-radius: 5px; }
        QProgressBar::chunk { background: #3daee9; }
        QInputDialog { background: #232629; color: #f0f0f0; }
    ''')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    gui = VoiceChangerGUI()
    gui.setWindowTitle('Chameleon ボイスチェンジャー v1.0')
    gui.setMinimumSize(520, 600)
    gui.show()
    ret = app.exec_()
    gui.save_config()
    sys.exit(ret)
