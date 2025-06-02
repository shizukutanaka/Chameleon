package main

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"

	"fyne.io/fyne/v2/app"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/widget"
	"fyne.io/fyne/v2"
)

type CycleEntry struct {
	Time   string
	Status string
	Detail string
	Cosine *float64
	L2     *float64
}

func parseEval(detail string) (cosine, l2 *float64) {
	var c, l float64
	if _, err := fmt.Sscanf(detail, "new=%*d,learn=%*s,eval=cosine_distance=%f\tl2_distance=%f", &c, &l); err == nil {
		return &c, &l
	}
	return nil, nil
}

func parseReport(path string) ([]CycleEntry, error) {
	entries := []CycleEntry{}
	f, err := os.Open(path)
	if err != nil {
		return entries, err
	}
	defer f.Close()
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		parts := strings.SplitN(line, "\t", 3)
		if len(parts) < 3 {
			continue
		}
		cosine, l2 := parseEval(parts[2])
		entries = append(entries, CycleEntry{
			Time:   parts[0],
			Status: parts[1],
			Detail: parts[2],
			Cosine: cosine,
			L2:     l2,
		})
	}
	return entries, nil
}

func main() {
	a := app.New()
	w := a.NewWindow("Cycle Report Dashboard")
	w.Resize(fyne.NewSize(800, 500))

	entries, err := parseReport("cycle_report.log")
	if err != nil {
		w.SetContent(widget.NewLabel("cycle_report.log not found"))
		w.ShowAndRun()
		return
	}

	// テーブルデータ作成
	head := []string{"Time", "Status", "Cosine", "L2", "Detail"}
	rows := [][]string{head}
	var cosines, l2s []float64
	for _, e := range entries {
		cstr, lstr := "", ""
		if e.Cosine != nil { cstr = fmt.Sprintf("%.4f", *e.Cosine); cosines = append(cosines, *e.Cosine) }
		if e.L2 != nil { lstr = fmt.Sprintf("%.4f", *e.L2); l2s = append(l2s, *e.L2) }
		rows = append(rows, []string{e.Time, e.Status, cstr, lstr, e.Detail})
	}
	table := widget.NewTable(
		func() (int, int) { return len(rows), len(head) },
		func() fyne.CanvasObject { return widget.NewLabel("") },
		func(i, j int, o fyne.CanvasObject) {
			label := o.(*widget.Label)
			label.SetText(rows[i][j])
		},
	)

	// 折れ線グラフ描画（internal.LineChart）
	graph := widget.NewLabel("[Cosine/L2グラフ: データ不足]")
	if len(cosines) > 1 {
		imported := false
		var linechartObj fyne.CanvasObject
		// Cosineグラフ
		linechartObj = LineChart("Cosine Distance", nil, cosines, color.RGBA{0,0,255,255})
		imported = true
		// L2グラフも重ねたい場合はLineChartを拡張
		if imported {
			graph = linechartObj
		}
	}

	w.SetContent(container.NewVBox(
		widget.NewLabel("Cycle Report Dashboard (アプリ内ウインドウ版)"),
		graph,
		table,
	))
	w.ShowAndRun()
}

