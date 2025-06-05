import sys
import os
import threading
import subprocess
import yaml
import shutil
import winshell
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog, QSpinBox, QMessageBox, QSystemTrayIcon, QMenu
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QCoreApplication, Qt

CONFIG_PATH = 'config.yaml'

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_config(cfg):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        yaml.safe_dump(cfg, f, allow_unicode=True)

class ConfigWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Chameleon 設定')
        self.cfg = load_config() or {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        # 動画保存先
        self.video_dir = QLineEdit(self.cfg.get('video_dir', 'E:/ChameleonData/videos'))
        btn_video_dir = QPushButton('参照')
        btn_video_dir.clicked.connect(lambda: self.select_dir(self.video_dir))
        row1 = QHBoxLayout(); row1.addWidget(QLabel('動画保存先:')); row1.addWidget(self.video_dir); row1.addWidget(btn_video_dir)
        # MFCC保存先
        self.mfcc_dir = QLineEdit(self.cfg.get('mfcc_dir', 'E:/ChameleonData/mfccs'))
        btn_mfcc_dir = QPushButton('参照')
        btn_mfcc_dir.clicked.connect(lambda: self.select_dir(self.mfcc_dir))
        row2 = QHBoxLayout(); row2.addWidget(QLabel('MFCC保存先:')); row2.addWidget(self.mfcc_dir); row2.addWidget(btn_mfcc_dir)
        # モデル保存先
        self.model_dir = QLineEdit(self.cfg.get('model_dir', 'E:/ChameleonData/models'))
        btn_model_dir = QPushButton('参照')
        btn_model_dir.clicked.connect(lambda: self.select_dir(self.model_dir))
        row3 = QHBoxLayout(); row3.addWidget(QLabel('モデル保存先:')); row3.addWidget(self.model_dir); row3.addWidget(btn_model_dir)
        # サイクル間隔
        self.interval = QSpinBox(); self.interval.setRange(1, 1440)
        self.interval.setValue(self.cfg.get('interval_min', 60))
        row4 = QHBoxLayout(); row4.addWidget(QLabel('サイクル間隔(分):')); row4.addWidget(self.interval)
        # 言語
        self.lang = QLineEdit(self.cfg.get('lang', 'en'))
        row5 = QHBoxLayout(); row5.addWidget(QLabel('言語:')); row5.addWidget(self.lang)
        # 保存ボタン
        btn_save = QPushButton('保存')
        btn_save.clicked.connect(self.save_cfg)
        # 開始ボタン
        btn_start = QPushButton('自動運用開始')
        btn_start.clicked.connect(self.start_cycle)
        # レイアウト追加
        for row in [row1, row2, row3, row4, row5]:
            layout.addLayout(row)
        layout.addWidget(btn_save)
        layout.addWidget(btn_start)
        self.setLayout(layout)

    def select_dir(self, lineedit):
        d = QFileDialog.getExistingDirectory(self, 'ディレクトリ選択')
        if d:
            lineedit.setText(d)

    def save_cfg(self):
        cfg = {
            'video_dir': self.video_dir.text(),
            'mfcc_dir': self.mfcc_dir.text(),
            'model_dir': self.model_dir.text(),
            'interval_min': self.interval.value(),
            'lang': self.lang.text(),
        }
        save_config(cfg)
        QMessageBox.information(self, '保存', '設定を保存しました')

    def start_cycle(self):
        self.save_cfg()
        self.hide()
        t = threading.Thread(target=run_scheduler, daemon=True)
        t.start()
        QMessageBox.information(self, '開始', '自動運用をバックグラウンドで開始しました')
        self.close()

def run_scheduler():
    # サイレントでmain_scheduler.pyを起動
    subprocess.Popen([sys.executable, 'main_scheduler.py'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def add_to_startup():
    # Windowsスタートアップフォルダにショートカットを自動作成
    startup = winshell.startup()
    exe = sys.executable
    script = os.path.abspath(__file__)
    shortcut = os.path.join(startup, "Chameleon.lnk")
    if not os.path.exists(shortcut):
        import pythoncom
        from win32com.shell import shell, shellcon
        from win32com.client import Dispatch
        shell = Dispatch('WScript.Shell')
        shortcut_obj = shell.CreateShortCut(shortcut)
        shortcut_obj.Targetpath = exe
        shortcut_obj.Arguments = f'"{script}"'
        shortcut_obj.WorkingDirectory = os.path.dirname(script)
        shortcut_obj.IconLocation = os.path.join(os.path.dirname(script), 'chameleon.ico')
        shortcut_obj.save()

import time
import atexit
from PyQt5.QtWidgets import QAction
import webbrowser

def lockfile_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chameleon.lock')

def create_lock():
    path = lockfile_path()
    if os.path.exists(path):
        QMessageBox.critical(None, "多重起動防止", "Chameleonは既に起動中です。タスクトレイを確認してください。")
        sys.exit(0)
    with open(path, 'w') as f:
        f.write(str(os.getpid()))
    atexit.register(lambda: os.remove(path))

def show_tray():
    app = QApplication(sys.argv)
    create_lock()
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chameleon.ico')
    if not os.path.exists(icon_path):
        QMessageBox.critical(None, "エラー", f"アイコンファイルが見つかりません: {icon_path}")
    tray = QSystemTrayIcon(QIcon(icon_path))
    tray.setToolTip('Chameleon Voice Changer')
    menu = QMenu()
    action_show = QAction('設定を開く')
    action_pause = QAction('一時停止')
    action_resume = QAction('再開')
    action_cycle = QAction('今すぐ1サイクル')
    action_log = QAction('ログを開く')
    action_status = QAction('詳細状態表示')
    action_quit = QAction('終了')
    menu.addAction(action_show)
    menu.addAction(action_pause)
    menu.addAction(action_resume)
    menu.addAction(action_cycle)
    menu.addAction(action_log)
    menu.addAction(action_status)
    menu.addSeparator()
    menu.addAction(action_quit)
    tray.setContextMenu(menu)
    win = ConfigWindow()
    win.setWindowFlag(Qt.Tool)
    win.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    win.hide()
    action_show.triggered.connect(win.show)
    def pause_cycle():
        with open('chameleon.pause', 'w') as f: f.write('pause')
        tray.showMessage('Chameleon', 'サイクルを一時停止しました', QSystemTrayIcon.Information)
    def resume_cycle():
        if os.path.exists('chameleon.pause'):
            os.remove('chameleon.pause')
        tray.showMessage('Chameleon', 'サイクルを再開しました', QSystemTrayIcon.Information)
    def manual_cycle():
        with open('chameleon.manual', 'w') as f: f.write('manual')
        tray.showMessage('Chameleon', '1サイクル即時実行をリクエストしました', QSystemTrayIcon.Information)
    def open_log():
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cycle_report.log')
        if os.path.exists(log_path):
            webbrowser.open(log_path)
        else:
            QMessageBox.information(None, 'ログ', 'cycle_report.logがありません')
    def show_status():
        status_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chameleon.status')
        report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cycle_report.log')
        status = '不明'
        if os.path.exists(status_path):
            with open(status_path, 'r', encoding='utf-8') as f:
                status = f.read().strip()
        last_reports = []
        timeline = ''
        if os.path.exists(report_path):
            with open(report_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # サイクル終了行を抽出し直近1件のタイムラインも表示
                cycle_indices = [i for i, l in enumerate(lines) if 'サイクルNo:' in l]
                if cycle_indices:
                    last_idx = cycle_indices[-1]
                    # 直前の==== サイクル開始: ... ==== からサイクルNoまでの範囲を抜き出す
                    start_idx = last_idx
                    while start_idx > 0 and not lines[start_idx].startswith('==== Chameleonサイクル開始:'):
                        start_idx -= 1
                    timeline_lines = lines[start_idx:last_idx+1]
                    # 工程タイムスタンプのみ抽出
                    timeline = ''.join([l for l in timeline_lines if any(x in l for x in ['downloading','extracting','inferring'])])
                # サイクル履歴は直近5件
                cycle_lines = [l for l in lines if 'サイクルNo:' in l]
                last_reports = cycle_lines[-5:] if len(cycle_lines) >= 1 else lines[-5:]
        msg = f'現在の状態: {status}\n---最新サイクル履歴---\n' + ''.join(last_reports)
        if timeline:
            msg += '\n---最新サイクル工程タイムライン---\n' + timeline
        QMessageBox.information(None, 'Chameleon詳細状態', msg)
    action_pause.triggered.connect(pause_cycle)
    action_resume.triggered.connect(resume_cycle)
    action_cycle.triggered.connect(manual_cycle)
    action_log.triggered.connect(open_log)
    action_status.triggered.connect(show_status)
    action_quit.triggered.connect(QCoreApplication.quit)
    tray.show()
    add_to_startup()
    # 通知監視スレッド
    def notify_watcher():
        queue_path = 'notify_queue.txt'
        last = ''
        while True:
            if os.path.exists(queue_path):
                with open(queue_path, 'r', encoding='utf-8') as f:
                    msg = f.read().strip()
                if msg and msg != last:
                    tray.showMessage('Chameleon', msg, QSystemTrayIcon.Information)
                    last = msg
                os.remove(queue_path)
            time.sleep(2)
    threading.Thread(target=notify_watcher, daemon=True).start()

    # サイクル状態監視スレッド（アイコン切替）
    def status_icon_watcher():
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_normal = os.path.join(base_dir, 'chameleon.ico')
        icon_working = os.path.join(base_dir, 'chameleon_working.ico')
        icon_error = os.path.join(base_dir, 'chameleon_error.ico')
        last_status = ''
        while True:
            status = 'idle'
            if os.path.exists('chameleon.status'):
                with open('chameleon.status', 'r', encoding='utf-8') as f:
                    status = f.read().strip()
            if status != last_status:
                if status == 'working' and os.path.exists(icon_working):
                    tray.setIcon(QIcon(icon_working))
                elif status == 'error' and os.path.exists(icon_error):
                    tray.setIcon(QIcon(icon_error))
                else:
                    tray.setIcon(QIcon(icon_normal))
                last_status = status
            time.sleep(2)
    threading.Thread(target=status_icon_watcher, daemon=True).start()

    sys.exit(app.exec_())

if __name__ == '__main__':
    show_tray()
