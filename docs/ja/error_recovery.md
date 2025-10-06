# エラーリカバリーシステム - Chameleon Audio Tool

## 🎯 概要

このドキュメントでは、Chameleon Audio Tool v1.0.0 市販リリースで実装された包括的なエラーリカバリーシステムについて説明します。このエラーリカバリーフレームワークは、エンタープライズグレードの耐障害性、自動回復機構、堅牢なエラーハンドリング機能を提供します。

## 📋 エラーリカバリーカテゴリ

### 自動エラーリカバリー

**処理エラーリカバリー**
```python
import logging
import time
import threading
from chameleon_audio.recovery import RecoveryManager

class ProcessingRecoveryManager:
    def __init__(self):
        self.recovery_attempts = {}
        self.max_recovery_attempts = 3
        self.recovery_delay = 1.0  # 秒

    def execute_with_recovery(self, operation_func, *args, **kwargs):
        """自動エラーリカバリー付きで操作を実行"""
        operation_name = operation_func.__name__
        attempt = 0

        while attempt < self.max_recovery_attempts:
            try:
                # 操作を試行
                result = operation_func(*args, **kwargs)
                self._log_successful_recovery(operation_name, attempt)
                return result

            except (IOError, OSError) as e:
                attempt += 1
                if attempt >= self.max_recovery_attempts:
                    raise e

                # I/Oエラーの回復戦略
                recovery_strategy = self._get_io_recovery_strategy(e, attempt)
                self._execute_recovery_strategy(recovery_strategy, operation_name, attempt)

            except (MemoryError, OverflowError) as e:
                attempt += 1
                if attempt >= self.max_recovery_attempts:
                    raise e

                # メモリエラーの回復戦略
                recovery_strategy = self._get_memory_recovery_strategy(e, attempt)
                self._execute_recovery_strategy(recovery_strategy, operation_name, attempt)

            except Exception as e:
                # 想定外エラーはログに残して中断
                self._log_unrecoverable_error(operation_name, e)
                raise e

`core.py` では、この考え方を `ServiceDegradationManager` として実装しています。バッチ処理のサマリには、現在のサービスレベルや遷移 (`full` / `degraded` / `basic` / `minimal`)、そして原因（例: `timeout`, `high_severity_errors`, `high_failure_rate`）が含まれます。CLI のバッチ出力にもこれらの情報が表示され、システムが保護モードへ移行した場合に運用者が即座に把握できます。

状態復旧は `StateRecoveryManager` が担当します。各バッチ処理の完了時に、`~/.chameleon_state/`（または `CHAMELEON_STATE_DIR` で指定したディレクトリ）へ JSON スナップショットを保存します。スナップショットにはサービスレベルを含むサマリ情報が格納され、中断後の再開時にも継続性を確保できます。CLI のバッチサマリは保存先パスと直前のスナップショットのタイムスタンプを表示し、進捗の追跡を容易にします。

### 回復メトリクスの可視化

`RecoveryManager` は自動リトライが発生するたびに集計メトリクスを更新します。コアのバッチサマリにこれらの値が含まれ、`batch` コマンド実行時に CLI で出力されます。

- `total_attempts`: リカバリ対象として実行された処理の総数
- `total_retries`: エラー後に実施したリトライ回数
- `successful_recoveries`: リトライ後に成功した処理数
- `failed_recoveries`: 全リトライが失敗した処理数
- `memory_errors`: `MemoryError` によるリカバリサイクル数
- `os_errors`: `OSError` によるリカバリサイクル数

これらのメトリクスは、リカバリ機構の介入頻度や主要なエラー種別を迅速に把握するために役立ちます。サービスレベル情報と組み合わせて監視することで、異常な失敗傾向を早期に検出できます。

```text
$ chameleon batch ./audio normalize --progress
Batch processing complete [normalize]: 18/20 successful, 2 failed
  Service level transition: full → basic (reasons: high_severity_errors)
  Recovery state saved: /home/user/.chameleon_state/batch_state_20250927T080559123456Z.json
  Previous state timestamp: 20250926T233002849115Z
  Recovery metrics:
    failed_recoveries: 1
    memory_errors: 0
    os_errors: 2
    successful_recoveries: 1
    total_attempts: 20
    total_retries: 3
```

`BatchProcessor.process_directory()` は標準ロガー経由でメトリクスのペイロードも出力します。ログ収集やメトリクス監視と連携し、リトライ量の増加や `failed_recoveries` の増加を検知できるよう設定してください。

バッチ処理から利用者へ表示するエラーメッセージは、絶対パスや内部ディレクトリが含まれないようサニタイズされます。詳細なパス情報は `result.data` に保持されるため、運用側は内部情報を共有せずに診断できます。
            # バックアップを保存
            with open(self.state_file, 'w') as f:
                json.dump(state_backup, f, indent=2)

            # 古いバックアップをクリーンアップ
            self._cleanup_old_backups()

        except Exception as e:
            logging.error(f"Failed to create state backup: {e}")

    def recover_from_state_backup(self):
        """バックアップからアプリケーション状態を回復"""
        try:
            if not os.path.exists(self.state_file):
                return None

            with open(self.state_file, 'r') as f:
                state_backup = json.load(f)

            # チェックサムを検証
            expected_checksum = state_backup.get('checksum')
            actual_checksum = self._calculate_state_checksum(state_backup.get('state', {}))

            if expected_checksum != actual_checksum:
                logging.error("State backup checksum mismatch - possible corruption")
                return None

            recovered_state = state_backup.get('state', {})
            logging.info(f"Successfully recovered state from backup: {state_backup.get('timestamp')}")

            return recovered_state

        except Exception as e:
            logging.error(f"Failed to recover state from backup: {e}")
            return None
```

## 🔧 エラーハンドリングと回復

### グレースフルデグラデーション

**サービス低下管理**
```python
class GracefulDegradationManager:
    def __init__(self):
        self.service_levels = {
            "full": 1.0,
            "degraded": 0.7,
            "basic": 0.4,
        }
        self.current_service_level = "full"

    def handle_service_degradation(self, error_type, severity):
        """エラー条件に基づいてサービス低下を処理"""
        if severity == "critical":
            self._degrade_to_minimal()
        elif severity == "high":
            self._degrade_to_basic()
        elif severity == "medium":
            self._degrade_to_degraded()

        logging.warning(
            f"Service degraded to {self.current_service_level} due to {error_type} "
            f"(severity: {severity})"
        )

    def _degrade_to_minimal(self):
        """最小サービスレベルに低下"""
        self.current_service_level = "minimal"
        # 必須ではない機能を無効化
        self._disable_advanced_features()
        self._reduce_memory_usage()
        self._simplify_ui()

    def _degrade_to_basic(self):
        """基本サービスレベルに低下"""
        self.current_service_level = "basic"
        # 一部の高度な機能を無効化
        self._disable_performance_features()
        self._reduce_functionality()

    def _degrade_to_degraded(self):
        """低下サービスレベルに低下"""
        self.current_service_level = "degraded"
        # 機能を維持しつつパフォーマンスを低下
        self._reduce_performance()
        self._increase_timeouts()
```

## 📊 回復監視とレポート

### 回復指標

**パフォーマンス監視**
```python
class RecoveryMetricsCollector:
    def __init__(self):
        self.recovery_metrics = {
            "total_errors": 0,
            "recovered_errors": 0,
            "unrecoverable_errors": 0,
            "recovery_attempts": 0,
            "successful_recoveries": 0,
            "average_recovery_time": 0.0
        }

    def record_recovery_attempt(self, error_type, recovery_strategy, success, recovery_time):
        """回復試行指標を記録"""
        self.recovery_metrics["total_errors"] += 1
        self.recovery_metrics["recovery_attempts"] += 1

        if success:
            self.recovery_metrics["successful_recoveries"] += 1
            self.recovery_metrics["recovered_errors"] += 1
        else:
            self.recovery_metrics["unrecoverable_errors"] += 1

        # 平均回復時間を更新
        if self.recovery_metrics["successful_recoveries"] > 0:
            self.recovery_metrics["average_recovery_time"] = (
                (self.recovery_metrics["average_recovery_time"] * (self.recovery_metrics["successful_recoveries"] - 1) + recovery_time) /
                self.recovery_metrics["successful_recoveries"]
            )

    def get_recovery_rate(self):
        """回復成功率を計算"""
        if self.recovery_metrics["total_errors"] == 0:
            return 1.0
        return self.recovery_metrics["recovered_errors"] / self.recovery_metrics["total_errors"]

    def generate_recovery_report(self):
        """包括的な回復レポートを生成"""
        return {
            "summary": {
                "total_errors": self.recovery_metrics["total_errors"],
                "recovery_rate": self.get_recovery_rate(),
                "average_recovery_time": self.recovery_metrics["average_recovery_time"]
            },
            "detailed_metrics": self.recovery_metrics,
            "recommendations": self._generate_recovery_recommendations()
        }
```

## 🎯 市販レベルステータス

**エラーリカバリーシステム - 完了** ✅

**回復カテゴリ**: 自動エラーリカバリー、システム状態回復、ネットワークエラーリカバリー、グレースフルデグラデーション、エラー分析
**監視**: 回復指標、パフォーマンス監視、影響評価
**エンタープライズ対応**: ✅

---

*Chameleon Audio Tool - エラーリカバリーシステム完了*
