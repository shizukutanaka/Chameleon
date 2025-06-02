package main

import (
	"gopkg.in/yaml.v2"
	"io/ioutil"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

type Config struct {
	Lang               string   `yaml:"lang"`
	IntervalMin        int      `yaml:"interval_min"`
	MaxDownload        int      `yaml:"max_download"`
	VideoDir           string   `yaml:"video_dir"`
	MfccDir            string   `yaml:"mfcc_dir"`
	ModelDir           string   `yaml:"model_dir"`
	VoiceFeaturesCsv   string   `yaml:"voice_features_csv"`
	PeopleMetadataCsv  string   `yaml:"people_metadata_csv"`
	PythonPath         string   `yaml:"python_path"`
	ExtractMfccPy      string   `yaml:"extract_mfcc_py"`
	ExtractPeoplePy    string   `yaml:"extract_people_py"`
	DiffusionInferPy   string   `yaml:"diffusion_infer_py"`
	VideoCrawlerPy     string   `yaml:"video_crawler_py"`
	CycleReport        string   `yaml:"cycle_report"`
	DuplicateThreshold float64  `yaml:"duplicate_threshold"`
	UrlList            []string `yaml:"url_list"`
	UrlListFile        string   `yaml:"url_list_file"`
	DownloadedUrlsFile string   `yaml:"downloaded_urls_file"`
}

func loadConfig(path string) (*Config, error) {
	data, err := ioutil.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var cfg Config
	err = yaml.Unmarshal(data, &cfg)
	if err != nil {
		return nil, err
	}
	return &cfg, nil
}

func validateConfig(cfg *Config) error {
	empty := func(s string) bool { return len(s) == 0 }
	missing := []string{}
	if empty(cfg.Lang) { missing = append(missing, "lang") }
	if empty(cfg.VideoDir) { missing = append(missing, "video_dir") }
	if empty(cfg.ModelDir) { missing = append(missing, "model_dir") }
	if empty(cfg.PythonPath) { missing = append(missing, "python_path") }
	if empty(cfg.ExtractMfccPy) { missing = append(missing, "extract_mfcc_py") }
	if empty(cfg.ExtractPeoplePy) { missing = append(missing, "extract_people_py") }
	if empty(cfg.DiffusionInferPy) { missing = append(missing, "diffusion_infer_py") }
	if empty(cfg.VideoCrawlerPy) { missing = append(missing, "video_crawler_py") }
	if len(missing) > 0 {
		return fmt.Errorf("config.yamlの必須項目が不足: %v", missing)
	}
	return nil
}

func countLines(path string) int {
	f, err := os.Open(path)
	if err != nil {
		return 0
	}
	defer f.Close()
	count := 0
	buf := make([]byte, 32*1024)
	for {
		n, err := f.Read(buf)
		for i := 0; i < n; i++ {
			if buf[i] == '\n' {
				count++
			}
		}
		if err != nil {
			break
		}
	}
	return count
}

func runLearningCycle(cfg *Config, learnLang, videoDir string, reportFile string, retryCount int) {
	cycleTime := time.Now().Format("2006-01-02 15:04:05")
	fmt.Printf("[サイクル開始] %s\n", cycleTime)
	var lastErr error
	// --- サイクル前の特徴量件数 ---
	featuresCsv := cfg.VoiceFeaturesCsv
	beforeCount := countLines(featuresCsv)
	fmt.Printf("[自動学習] サイクル前の特徴量件数: %d\n", beforeCount)

	for attempt := 1; attempt <= retryCount; attempt++ {
		fmt.Printf("[自動学習] 試行 %d/%d\n", attempt, retryCount)
		// --- 動画収集 ---
		var urlList []string
		if cfg.UrlListFile != "" {
			// 外部ファイルからURLリストを読み込む
			if urls, err := readLines(cfg.UrlListFile); err == nil {
				urlList = urls
			}
		}
		if len(cfg.UrlList) > 0 {
			urlList = append(urlList, cfg.UrlList...)
		}
		used := map[string]bool{}
		if cfg.DownloadedUrlsFile != "" {
			if done, err := readLines(cfg.DownloadedUrlsFile); err == nil {
				for _, u := range done { used[u] = true }
			}
		}
		for _, url := range urlList {
			if used[url] { continue }
			cmd := exec.Command(cfg.PythonPath, cfg.VideoCrawlerPy, "--url", url, "--outdir", videoDir, "--config", "config.yaml")
			cmd.Stdout = os.Stdout
			cmd.Stderr = os.Stderr
			if err := cmd.Run(); err != nil {
				fmt.Println("動画自動収集エラー:", err)
				logError(err)
				lastErr = err
				continue
			}
			if cfg.DownloadedUrlsFile != "" {
				appendLine(cfg.DownloadedUrlsFile, url)
			}
		}
		if len(urlList) == 0 {
			cmd := exec.Command(cfg.PythonPath, cfg.VideoCrawlerPy, "--lang", learnLang, "--max", fmt.Sprint(cfg.MaxDownload), "--outdir", videoDir, "--config", "config.yaml")
			cmd.Stdout = os.Stdout
			cmd.Stderr = os.Stderr
			if err := cmd.Run(); err != nil {
				fmt.Println("動画自動収集エラー:", err)
				logError(err)
				lastErr = err
				continue
			}
		}
		// --- 音声抽出・学習 ---
		files, _ := os.ReadDir(videoDir)
		for _, f := range files {
			if f.IsDir() || !(strings.HasSuffix(f.Name(), ".mp3") || strings.HasSuffix(f.Name(), ".m4a") || strings.HasSuffix(f.Name(), ".webm") || strings.HasSuffix(f.Name(), ".wav")) {
				continue
			}
			inputAudio := filepath.Join(videoDir, f.Name())
			mfccOutput := inputAudio + ".mfcc.csv"
			if _, err := os.Stat(mfccOutput); err == nil {
				fmt.Println("[自動学習] 既に学習済み: ", mfccOutput)
				continue
			}
			metaDesc := ""
			metaPath := inputAudio + ".info.json"
			if _, err := os.Stat(metaPath); err == nil {
				metaDesc = extractDescriptionFromMeta(metaPath)
			}
			if metaDesc != "" {
				cmd := exec.Command(cfg.PythonPath, cfg.ExtractPeoplePy, "--desc", metaDesc, "--output", cfg.PeopleMetadataCsv, "--config", "config.yaml")
				cmd.Stdout = os.Stdout
				cmd.Stderr = os.Stderr
				_ = cmd.Run()
			}
			// MFCC抽出
			cmd := exec.Command(cfg.PythonPath, cfg.ExtractMfccPy, "--input", inputAudio, "--output", mfccOutput, "--config", "config.yaml")
			cmd.Stdout = os.Stdout
			cmd.Stderr = os.Stderr
			if err := cmd.Run(); err != nil {
				fmt.Println("MFCC抽出エラー:", err)
				logError(err)
				lastErr = err
				continue
			}
			fmt.Println("[自動学習] MFCC抽出完了: ", mfccOutput)
		}
		// --- サイクル後の特徴量件数 ---
		afterCount := countLines(featuresCsv)
		fmt.Printf("[自動学習] サイクル後の特徴量件数: %d\n", afterCount)
		newCount := afterCount - beforeCount
		var learnResult, evalResult string
		if newCount > 0 {
			fmt.Printf("[自動学習] 新規データ%d件→モデル自動学習を実行\n", newCount)
			// --- Diffusionモデル自動学習 ---
			outWav := filepath.Join(videoDir, "autotest_"+time.Now().Format("20060102150405")+".wav")
			cmd := exec.Command(cfg.PythonPath, cfg.DiffusionInferPy, "--text", "自動学習テスト", "--voice", "auto", "--style", "auto", "--output", outWav, "--config", "config.yaml")
			cmd.Stdout = os.Stdout
			cmd.Stderr = os.Stderr
			if err := cmd.Run(); err != nil {
				fmt.Println("[自動学習] モデル学習エラー:", err)
				logError(err)
				learnResult = "fail"
			} else {
				fmt.Println("[自動学習] モデル学習成功: ", outWav)
				learnResult = "success"
				// --- モデル評価: 直近のinputAudioと生成outWavを比較 ---
				var latestInput string
				files, _ := os.ReadDir(videoDir)
				latestTime := int64(0)
				for _, f := range files {
					if f.IsDir() || !(strings.HasSuffix(f.Name(), ".mp3") || strings.HasSuffix(f.Name(), ".wav")) {
						continue
					}
					info, err := os.Stat(filepath.Join(videoDir, f.Name()))
					if err == nil && info.ModTime().Unix() > latestTime {
						latestTime = info.ModTime().Unix()
						latestInput = filepath.Join(videoDir, f.Name())
					}
				}
				if latestInput != "" && outWav != "" {
					cmdEval := exec.Command(cfg.PythonPath, "internal/audio/eval_mfcc_distance.py", "--ref", latestInput, "--gen", outWav, "--config", "config.yaml")
					output, err := cmdEval.CombinedOutput()
					if err != nil {
						evalResult = "eval_error"
						fmt.Println("[自動学習] モデル評価エラー:", err, string(output))
					} else {
						evalResult = strings.TrimSpace(string(output))
						fmt.Println("[自動学習] モデル評価結果:", evalResult)
					}
				} else {
					evalResult = "input_missing"
				}
			}
		} else {
			fmt.Println("[自動学習] 新規データなし→学習スキップ")
			learnResult = "skip"
		}
		// サイクル成功
		writeReport(reportFile, cycleTime, "success", fmt.Sprintf("new=%d,learn=%s,eval=%s", newCount, learnResult, evalResult))
		fmt.Printf("[サイクル成功] %s\n", cycleTime)

		// --- 評価しきい値チェック・Slack通知 ---
		cfgData, _ := ioutil.ReadFile("config.yaml")
		var cfgMap map[string]interface{}
		yaml.Unmarshal(cfgData, &cfgMap)
		notifyOnError, _ := cfgMap["notify_on_error"].(bool)
		evalThreshold, _ := cfgMap["eval_threshold"].(float64)
	
evalMetric, _ := cfgMap["eval_metric"].(string)
		webhookUrl, _ := cfgMap["slack_webhook_url"].(string)
		if notifyOnError && webhookUrl != "" && evalResult != "" && evalResult != "eval_error" && evalResult != "input_missing" {
			// 評価値をパース
			var evalVal float64
			if evalMetric == "cosine_distance" {
				_, err := fmt.Sscanf(evalResult, "cosine_distance=%f", &evalVal)
				if err == nil && evalVal > evalThreshold {
					msg := fmt.Sprintf(":warning: モデル評価値がしきい値を超過: %s > %.3f", evalResult, evalThreshold)
					exec.Command(cfg.PythonPath, "internal/audio/send_slack.py", "--message", msg, "--config", "config.yaml").Run()
				}
			}
			if evalMetric == "l2_distance" {
				_, err := fmt.Sscanf(evalResult, "cosine_distance=%f\tl2_distance=%f", new(float64), &evalVal)
				if err == nil && evalVal > evalThreshold {
					msg := fmt.Sprintf(":warning: モデル評価値がしきい値を超過: %s > %.3f", evalResult, evalThreshold)
					exec.Command(cfg.PythonPath, "internal/audio/send_slack.py", "--message", msg, "--config", "config.yaml").Run()
				}
			}
		}
		return
	}
	// サイクル失敗
	writeReport(reportFile, cycleTime, "fail", lastErr.Error())
	fmt.Printf("[サイクル失敗] %s: %v\n", cycleTime, lastErr)

	// --- 失敗時Slack通知 ---
	cfgData, _ := ioutil.ReadFile("config.yaml")
	var cfgMap map[string]interface{}
	yaml.Unmarshal(cfgData, &cfgMap)
	notifyOnError, _ := cfgMap["notify_on_error"].(bool)
	webhookUrl, _ := cfgMap["slack_webhook_url"].(string)
	if notifyOnError && webhookUrl != "" {
		exec.Command(cfg.PythonPath, "internal/audio/send_slack.py", "--message", fmt.Sprintf(":x: サイクル失敗: %v", lastErr), "--config", "config.yaml").Run()
	}
}

func writeReport(reportFile, cycleTime, status, detail string) {
	f, err := os.OpenFile(reportFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		fmt.Println("[レポート出力エラー]", err)
		return
	}
	defer f.Close()
	rec := fmt.Sprintf("%s\t%s\t%s\n", cycleTime, status, detail)
	f.WriteString(rec)
}

func main() {
	cfg, err := loadConfig("config.yaml")
	if err != nil {
		os.Exit(1)
	}
	intervalMin := cfg.IntervalMin
	for {
		cycleTime := time.Now().Format("2006-01-02 15:04:05")
		// 動画収集
		exec.Command(cfg.PythonPath, cfg.VideoCrawlerPy, "--lang", cfg.Lang, "--max", intToStr(cfg.MaxDownload), "--outdir", cfg.VideoDir, "--config", "config.yaml").Run()
		// 音声ファイル列挙
		files, _ := os.ReadDir(cfg.VideoDir)
		for _, f := range files {
			if f.IsDir() || !(strings.HasSuffix(f.Name(), ".mp3") || strings.HasSuffix(f.Name(), ".m4a") || strings.HasSuffix(f.Name(), ".webm") || strings.HasSuffix(f.Name(), ".wav")) {
				continue
			}
			inputAudio := filepath.Join(cfg.VideoDir, f.Name())
			mfccOutput := inputAudio + ".mfcc.csv"
			if _, err := os.Stat(mfccOutput); err == nil {
				continue
			}
			metaPath := inputAudio + ".info.json"
			metaDesc := ""
			if _, err := os.Stat(metaPath); err == nil {
				metaDesc = extractDescriptionFromMeta(metaPath)
			}
			if metaDesc != "" {
				exec.Command(cfg.PythonPath, cfg.ExtractPeoplePy, "--desc", metaDesc, "--output", cfg.PeopleMetadataCsv, "--config", "config.yaml").Run()
			}
			exec.Command(cfg.PythonPath, cfg.ExtractMfccPy, "--input", inputAudio, "--output", mfccOutput, "--config", "config.yaml").Run()
		}
		// モデル学習
		outWav := filepath.Join(cfg.VideoDir, "autotest_"+time.Now().Format("20060102150405")+".wav")
		exec.Command(cfg.PythonPath, cfg.DiffusionInferPy, "--text", "自動学習テスト", "--voice", "auto", "--style", "auto", "--output", outWav, "--config", "config.yaml").Run()
		// 評価（オプション）
		// 必要ならここでPython評価スクリプト呼び出し
		// サイクル記録
		appendCycleReport(cfg.CycleReport, cycleTime)
		time.Sleep(time.Duration(intervalMin) * time.Minute)
	}
}

func intToStr(i int) string {
	return strconv.Itoa(i)
}

func extractDescriptionFromMeta(metaPath string) string {
	// 必要最小限のdescription抽出
	return ""
}

func readLines(path string) ([]string, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var lines []string
	scan := bufio.NewScanner(f)
	for scan.Scan() {
		line := strings.TrimSpace(scan.Text())
		if line != "" {
			lines = append(lines, line)
		}
	}
	return lines, scan.Err()
}

func appendLine(path, line string) {
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return
	}
	defer f.Close()
	f.WriteString(line + "\n")
}

func appendCycleReport(reportFile, cycleTime string) {
	f, err := os.OpenFile(reportFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return
	}
	defer f.Close()
	f.WriteString(cycleTime + "\n")
}

	fmt.Println("== 軽量ボイスチェンジャー（Go版）==")
	cfg, err := loadConfig("config.yaml")
	if err != nil {
		fmt.Println("設定ファイル(config.yaml)の読み込みに失敗:", err)
		return
	}
	if err := validateConfig(cfg); err != nil {
		fmt.Println("[設定エラー]", err)
		return
	}
	// 言語・間隔などはconfig.yamlから取得
	learnLang := cfg.Lang
	intervalMin := cfg.IntervalMin
	retryCount := 3
	reportFile := "cycle_report.log"
	if cfg.LogFile != "" {
		reportFile = cfg.LogFile + ".cycle_report.log"
	}
	videoDir := cfg.VideoDir
	if learnLang == "" {
		fmt.Print("自動学習したい言語コードを入力（例: ja, en, zh、空Enterで手動指定）: ")
		fmt.Scanln(&learnLang)
	}
	if intervalMin <= 0 {
		fmt.Print("学習サイクル間隔（分）を指定してください（例: 60）: ")
		tmp := 0
		fmt.Scanln(&tmp)
		if tmp > 0 {
			intervalMin = tmp
		} else {
			intervalMin = 60
		}
	}
	os.MkdirAll(videoDir, 0755)
	fmt.Printf("[自動学習] 言語=%s, 間隔=%d分, 保存先=%s\n", learnLang, intervalMin, videoDir)
	// --- 自動学習スケジューラ ---
	go func() {
		ticker := time.NewTicker(time.Duration(intervalMin) * time.Minute)
		defer ticker.Stop()
		for {
			runLearningCycle(cfg, learnLang, videoDir, reportFile, retryCount)
			<-ticker.C
		}
	}()
	// --- 既存の手動CLI処理は残す ---
					err := exec.Command(cfg.PythonPath, cfg.ExtractMfccPy, "--input", inputAudio, "--output", mfccOutput, "--config", "config.yaml").Run()
					if err != nil {
						fmt.Println("MFCC抽出エラー:", err)
						logError(err)
						continue
					}
					fmt.Println("[自動学習] ", inputAudio, "→", mfccOutput)
					voiceLabel := learnLang
					styleLabel := "auto"
					err = appendFeaturesWithLabels(mfccOutput, voiceLabel, styleLabel, cfg.VoiceFeaturesCsv)
					if err != nil {
						fmt.Println("特徴量保存エラー:", err)
						logError(err)
						continue
					}
				}
				fmt.Printf("[自動学習] このサイクル完了。%d分後に再実行します\n", intervalMin)
			}
			time.Sleep(time.Duration(intervalMin) * time.Minute)
		}
	}

	// --- ここから従来の手動処理（省略せず残す） ---
	if len(os.Args) < 2 {
		fmt.Println("使い方: go run main.go <動画ファイルパス>")
		return
	}
	videoPath := os.Args[1]
	outputAudio := "output.wav"

	fmt.Println("動画ファイル:", videoPath)
	fmt.Println("音声抽出中...")
	err := extractAudio(videoPath, outputAudio)
	if err != nil {
		fmt.Println("音声抽出エラー:", err)
		return
	}
	fmt.Println("音声抽出成功: ", outputAudio)

	// MFCC特徴量抽出（Pythonスクリプト呼び出し）
	mfccOutput := "output_mfcc.csv"
	err = extractMFCC(outputAudio, mfccOutput)
	if err != nil {
		fmt.Println("MFCC抽出エラー:", err)
		return
	}
	fmt.Println("MFCC特徴量抽出成功: ", mfccOutput)

	// ラベル入力
	var voiceLabel, styleLabel string
	fmt.Print("声のラベルを入力してください: ")
	fmt.Scanln(&voiceLabel)
	fmt.Print("話し方のラベルを入力してください: ")
	fmt.Scanln(&styleLabel)

	// 特徴量CSVにラベル付与して蓄積
	err = appendFeaturesWithLabels(mfccOutput, voiceLabel, styleLabel, "models/voice_features.csv")
	if err != nil {
		fmt.Println("特徴量保存エラー:", err)
		return
	}
	fmt.Println("学習データ保存完了: models/voice_features.csv")

	// --- プロンプト入力と特徴量検索 ---
	fmt.Println("\n== プロンプトによる声質検索 ==")
	var promptVoice, promptStyle, promptText string
	fmt.Print("出力したい声のラベル: ")
	fmt.Scanln(&promptVoice)
	fmt.Print("出力したい話し方のラベル: ")
	fmt.Scanln(&promptStyle)
	fmt.Print("喋らせたいテキスト: ")
	fmt.Scanln(&promptText)

	found, err := searchFeaturesByLabel("models/voice_features.csv", promptVoice, promptStyle)
	if err != nil {
		fmt.Println("検索エラー:", err)
		return
	}
	if found {
		fmt.Println("該当する特徴量が見つかりました。DiffusionモデルAPIで高速変換を実行します。")
		// DiffusionモデルAPIサーバへリクエスト
		outputWav := "output_diffusion.wav"
		err := callDiffusionLocal(promptText, promptVoice, promptStyle, outputWav)
		if err != nil {
			fmt.Println("Diffusionモデル推論エラー:", err)
			logError(err)
			return
		}
		fmt.Println("変換音声ファイル出力: ", outputWav)
		// 自動再生（Windows用）
		err = playAudio(outputWav)
		if err != nil {
			fmt.Println("音声自動再生エラー:", err)
			logError(err)
		}
	} else {
		fmt.Println("該当する特徴量が見つかりませんでした。")
	}
}

// DiffusionモデルAPIサーバ呼び出し例
// ローカルDiffusionモデル推論呼び出し
func callDiffusionLocal(text, voice, style, outWav string) error {
	modelPath := findFileWithExt("models", ".pth")
	configPath := findFileWithExt("models", ".json")
	cmd := exec.Command("python", "internal/audio/diffusion_infer.py", "--text", text, "--voice", voice, "--style", style, "--output", outWav)
	if modelPath != "" {
		cmd.Args = append(cmd.Args, "--model", modelPath)
	}
	if configPath != "" {
		cmd.Args = append(cmd.Args, "--config", configPath)
	}
	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("diffusion_infer.py失敗: %v\n出力: %s", err, string(output))
	}
	return nil
}

// modelsディレクトリから指定拡張子のファイルを1つ探す
func findFileWithExt(dir, ext string) string {
	files, err := os.ReadDir(dir)
	if err != nil {
		return ""
	}
	for _, f := range files {
		if !f.IsDir() && strings.HasSuffix(f.Name(), ext) {
			return filepath.Join(dir, f.Name())
		}
	}
	return ""
}

// info.jsonからdescriptionを抽出
func extractDescriptionFromMeta(metaPath string) string {
	f, err := os.Open(metaPath)
	if err != nil {
		return ""
	}
	defer f.Close()
	var meta struct {
		Description string `json:"description"`
	}
	dec := json.NewDecoder(f)
	_ = dec.Decode(&meta)
	return meta.Description
}

// config.jsonからAPI URLを読み込む
// エラーログ出力
func logError(err error) {
	f, ferr := os.OpenFile("error.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if ferr != nil {
		return
	}
	defer f.Close()
	t := time.Now().Format("2006-01-02 15:04:05")
	f.WriteString(fmt.Sprintf("[%s] %v\n", t, err))
}

// 音声自動再生（Windows: PowerShell）
func playAudio(wav string) error {
	cmd := exec.Command("powershell", "-c", "Start-Process", wav)
	return cmd.Run()
}



func searchFeaturesByLabel(csvPath, voiceLabel, styleLabel string) (bool, error) {
	file, err := os.Open(csvPath)
	if err != nil {
		return false, err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		fields := strings.Split(line, ",")
		if len(fields) < 2 {
			continue
		}
		if fields[len(fields)-2] == voiceLabel && fields[len(fields)-1] == styleLabel {
			return true, nil
		}
	}
	return false, scanner.Err()
}

func appendFeaturesWithLabels(mfccCsv, voiceLabel, styleLabel, outCsv string) error {
	inFile, err := os.Open(mfccCsv)
	if err != nil {
		return err
	}
	defer inFile.Close()

	outFile, err := os.OpenFile(outCsv, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return err
	}
	defer outFile.Close()

	scanner := bufio.NewScanner(inFile)
	for scanner.Scan() {
		line := scanner.Text()
		// 末尾にラベル2つを追加
		outFile.WriteString(line + "," + voiceLabel + "," + styleLabel + "\n")
	}
	return scanner.Err()
}

func extractMFCC(wavPath, csvPath string) error {
	cmd := exec.Command("python", "internal/audio/extract_mfcc.py", wavPath, csvPath)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

func extractAudio(videoPath, outputPath string) error {
	cmd := exec.Command("ffmpeg", "-i", videoPath, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", outputPath)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}
