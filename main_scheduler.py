import os
import sys
import time
import subprocess
import yaml
import glob
import logging
from datetime import datetime

# --- 設定ファイル読み込み ---
def load_config(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def ensure_dirs(*dirs):
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def append_line(path, line):
    with open(path, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def run_subprocess(args, log_prefix):
    try:
        result = subprocess.run(args, capture_output=True, text=True)
        with open('cycle_report.log', 'a', encoding='utf-8') as clog:
            clog.write(f'[{log_prefix} STDOUT] {result.stdout}\n')
        if result.returncode != 0:
            with open('error.log', 'a', encoding='utf-8') as elog:
                elog.write(f'[{log_prefix} STDERR] {result.stderr}\n')
            logging.error(f'{log_prefix} ERROR: {result.stderr}')
        else:
            logging.info(f'{log_prefix} OK: {result.stdout}')
        return result.returncode == 0
    except Exception as e:
        with open('error.log', 'a', encoding='utf-8') as elog:
            elog.write(f'[{log_prefix} EXCEPTION] {e}\n')
        logging.error(f'{log_prefix} EXCEPTION: {e}')
        return False

def main():
    # ログ設定
    logging.basicConfig(filename='cycle_report.log', level=logging.INFO, format='%(asctime)s %(message)s')
    errlog = logging.FileHandler('error.log')
    errlog.setLevel(logging.ERROR)
    logging.getLogger().addHandler(errlog)

    config = load_config('config.yaml')
    video_dir = config.get('video_dir', 'E:/ChameleonData/videos')
    mfcc_dir = config.get('mfcc_dir', 'E:/ChameleonData/mfccs')
    pose_dir = config.get('pose_features_dir', 'E:/ChameleonData/poses')
    model_dir = config.get('model_dir', 'E:/ChameleonData/models')
    downloaded_urls_file = config.get('downloaded_urls_file', 'E:/ChameleonData/downloaded_urls.txt')
    people_metadata_csv = config.get('people_metadata_csv', 'E:/ChameleonData/people_metadata.csv')
    voice_features_csv = config.get('voice_features_csv', 'E:/ChameleonData/voice_features.csv')
    interval_min = 1  # テスト用に1分に短縮
    max_download = config.get('max_download', 3)
    learn_lang = config.get('lang', 'en')
    python_path = config.get('python_path', sys.executable)
    video_crawler_py = config.get('video_crawler_py', 'internal/audio/video_crawler.py')
    extract_people_py = config.get('extract_people_py', 'internal/audio/extract_people_info.py')
    extract_mfcc_py = config.get('extract_mfcc_py', 'internal/audio/extract_mfcc.py')
    diffusion_infer_py = config.get('diffusion_infer_py', 'internal/audio/diffusion_infer.py')

    ensure_dirs(video_dir, mfcc_dir, model_dir, pose_dir, os.path.dirname(downloaded_urls_file), os.path.dirname(people_metadata_csv), os.path.dirname(voice_features_csv))

    cycle_count = 0
    import glob
    while True:
        # 一時停止監視
        if os.path.exists('chameleon.pause'):
            print('[INFO] サイクル一時停止中...')
            with open('cycle_report.log', 'a', encoding='utf-8') as clog:
                clog.write('[INFO] サイクル一時停止中...\n')
            time.sleep(10)
            continue
        # 即時実行監視
        if os.path.exists('chameleon.manual'):
            os.remove('chameleon.manual')
            print('[INFO] 手動サイクル即時実行リクエストを検知')
        else:
            time.sleep(interval_min * 60)
        cycle_count += 1
        cycle_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cycle_start = time.time()
        # config.yaml バックアップ
        try:
            import shutil
            backup_name = 'config_{}.yaml'.format(datetime.now().strftime('%Y%m%d_%H%M%S'))
            shutil.copyfile('config.yaml', backup_name)
            # 古いバックアップ自動削除（30件だけ残す）
            backups = sorted(glob.glob('config_*.yaml'))
            if len(backups) > 30:
                for old in backups[:-30]:
                    os.remove(old)
        except Exception as e:
            print('[WARN] config.yaml バックアップ失敗:', e)
        # cycle_report.log自動クリーンアップ（最新3000行だけ残す）
        report_path = 'cycle_report.log'
        if os.path.exists(report_path):
            with open(report_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            if len(lines) > 3000:
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines[-3000:])
        print('\n==== Chameleonサイクル開始: {} ===='.format(cycle_time))
        with open('cycle_report.log', 'a', encoding='utf-8') as clog:
            clog.write('==== Chameleonサイクル開始: {} (No.{}) ====\n'.format(cycle_time, cycle_count))
        # サイクル状態: downloading
        with open('chameleon.status', 'w', encoding='utf-8') as s:
            s.write('downloading')
        download_start = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open('cycle_report.log', 'a', encoding='utf-8') as clog:
            clog.write('[{}] downloading START\n'.format(download_start))
        # 1. 動画収集
        ok = run_subprocess([
            python_path, video_crawler_py,
            '--lang', learn_lang,
            '--max', str(max_download),
            '--outdir', video_dir,
            '--config', 'config.yaml'
        ], 'video_crawler')
        download_end = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open('cycle_report.log', 'a', encoding='utf-8') as clog:
            clog.write('[{}] downloading END\n'.format(download_end))
        if not ok:
            msg = '[ERROR] 動画収集に失敗'
            print(msg)
            with open('error.log', 'a', encoding='utf-8') as elog:
                elog.write(msg + '\n')
            with open('notify_queue.txt', 'w', encoding='utf-8') as n:
                n.write('動画収集に失敗しました')
            with open('chameleon.status', 'w', encoding='utf-8') as s:
                s.write('error')
            continue
        # 2. 新規動画一覧取得
        movie_files = sorted(glob.glob(os.path.join(video_dir, '*.mp4')) + glob.glob(os.path.join(video_dir, '*.mkv')) + glob.glob(os.path.join(video_dir, '*.webm')))
        print('[INFO] 検出動画数: {}'.format(len(movie_files)))

        # --- 音声ファイル自動学習（Whisper文字起こし）---
        import whisper
        model = whisper.load_model("base")
        audio_exts = [".mp3", ".wav", ".m4a", ".opus"]
        audio_files = []
        for ext in audio_exts:
            audio_files += glob.glob(os.path.join(video_dir, f"*{ext}"))
        for audio_file in audio_files:
            txt_file = os.path.splitext(audio_file)[0] + ".txt"
            if os.path.exists(txt_file):
                continue  # すでに学習済みはスキップ
            print(f"[AUTO-LEARN] Transcribing {audio_file} ...")
            try:
                result = model.transcribe(audio_file, language=learn_lang)
                with open(txt_file, "w", encoding="utf-8") as f:
                    f.write(result["text"])
                with open('cycle_report.log', 'a', encoding='utf-8') as clog:
                    clog.write(f'[AUTO-LEARN] Transcribed {audio_file} -> {txt_file}\n')
            except Exception as e:
                with open('error.log', 'a', encoding='utf-8') as elog:
                    elog.write(f'[AUTO-LEARN ERROR] {audio_file}: {e}\n')

        for movie in movie_files:
            base = os.path.splitext(os.path.basename(movie))[0]
            # 3. 音声特徴量抽出
            extract_start = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open('chameleon.status', 'w', encoding='utf-8') as s:
                s.write('extracting')
            with open('cycle_report.log', 'a', encoding='utf-8') as clog:
                clog.write('[{}] extracting START ({})\n'.format(extract_start, base))
            mfcc_out = os.path.join(mfcc_dir, base + '.mfcc.csv')
            if not os.path.exists(mfcc_out):
                ok = run_subprocess([
                    python_path, extract_mfcc_py,
                    '--input', movie,
                    '--output', mfcc_out,
                    '--config', 'config.yaml'
                ], 'extract_mfcc')
                if not ok:
                    msg = '[ERROR] MFCC抽出失敗: {}'.format(movie)
                    print(msg)
                    with open('error.log', 'a', encoding='utf-8') as elog:
                        elog.write(msg + '\n')
                    with open('notify_queue.txt', 'w', encoding='utf-8') as n:
                        n.write('MFCC抽出失敗: {}'.format(movie))
                    with open('chameleon.status', 'w', encoding='utf-8') as s:
                        s.write('error')
            # 4. 動作特徴量抽出
            with open('chameleon.status', 'w', encoding='utf-8') as s:
                s.write('extracting')
            pose_out = os.path.join(pose_dir, base + '.pose.csv')
            if not os.path.exists(pose_out):
                ok = run_subprocess([
                    python_path, extract_pose_py,
                    '--input', movie,
                    '--output', pose_out
                ], 'extract_pose')
                if not ok:
                    msg = '[ERROR] 動作抽出失敗: {}'.format(movie)
                    print(msg)
                    with open('error.log', 'a', encoding='utf-8') as elog:
                        elog.write(msg + '\n')
                    with open('notify_queue.txt', 'w', encoding='utf-8') as n:
                        n.write('動作抽出失敗: {}'.format(movie))
                    with open('chameleon.status', 'w', encoding='utf-8') as s:
                        s.write('error')
            extract_end = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open('cycle_report.log', 'a', encoding='utf-8') as clog:
                clog.write('[{}] extracting END ({})\n'.format(extract_end, base))
            # 5. モデル推論（例: diffusion_infer）
            infer_start = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open('chameleon.status', 'w', encoding='utf-8') as s:
                s.write('inferring')
            with open('cycle_report.log', 'a', encoding='utf-8') as clog:
                clog.write('[{}] inferring START ({})\n'.format(infer_start, base))
            out_wav = os.path.join(model_dir, '{}.out.wav'.format(base))
            if not os.path.exists(out_wav):
                ok = run_subprocess([
                    python_path, diffusion_infer_py,
                    '--input', movie,
                    '--output', out_wav,
                    '--config', 'config.yaml'
                ], 'diffusion_infer')
                if not ok:
                    msg = '[ERROR] 推論失敗: {}'.format(movie)
                    print(msg)
                    with open('error.log', 'a', encoding='utf-8') as elog:
                        elog.write(msg + '\n')
                    with open('notify_queue.txt', 'w', encoding='utf-8') as n:
                        n.write('推論失敗: {}'.format(movie))
                    with open('chameleon.status', 'w', encoding='utf-8') as s:
                        s.write('error')
            infer_end = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open('cycle_report.log', 'a', encoding='utf-8') as clog:
                clog.write('[{}] inferring END ({})\n'.format(infer_end, base))
        cycle_end = time.time()
        elapsed = cycle_end - cycle_start
        msg = '==== サイクル終了: {} ===='.format(cycle_time)
        print(msg)
        # エラー有無判定
        error_occurred = False
        last_error = ''
        if os.path.exists('error.log'):
            with open('error.log', 'r', encoding='utf-8') as elog:
                lines = elog.readlines()
                if lines and lines[-1].startswith('[ERROR]') and cycle_time[:16] in lines[-1]:
                    error_occurred = True
                    last_error = lines[-1].strip()
        with open('cycle_report.log', 'a', encoding='utf-8') as clog:
            clog.write(msg + '\n')
            clog.write('サイクルNo: {} 経過: {:.1f}秒 結果: {} {}\n'.format(
                cycle_count, elapsed, '失敗' if error_occurred else '成功', last_error))
        with open('notify_queue.txt', 'w', encoding='utf-8') as n:
            n.write('Chameleon: サイクル完了!')
        with open('chameleon.status', 'w', encoding='utf-8') as s:
            s.write('idle')

if __name__ == '__main__':
    main()
