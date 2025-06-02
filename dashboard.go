package main

import (
	"bufio"
	"fmt"
	"html/template"
	"net/http"
	"os"
	"strings"
)

type CycleEntry struct {
	Time    string
	Status  string
	Detail  string
	Cosine  *float64
	L2      *float64
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

var tmpl = `<!DOCTYPE html>
<html>
<head>
<meta charset='utf-8'>
<title>Cycle Report Dashboard</title>
<script src='https://cdn.jsdelivr.net/npm/chart.js'></script>
<style>table{border-collapse:collapse}th,td{border:1px solid #aaa;padding:4px;}th{background:#eee}</style>
</head>
<body>
<h2>Cycle Report Dashboard</h2>
<canvas id="evalChart" width="700" height="260"></canvas>
<script>
const labels = [
{{range .}}{{if .Cosine}}'{{.Time}}',{{end}}{{end}}
];
const cosineData = [
{{range .}}{{if .Cosine}}{{printf "%.4f" .Cosine}},{{end}}{{end}}
];
const l2Data = [
{{range .}}{{if .L2}}{{printf "%.4f" .L2}},{{end}}{{end}}
];
const data = {
  labels: labels,
  datasets: [
    {
      label: 'Cosine Distance',
      data: cosineData,
      borderColor: 'blue',
      fill: false
    },
    {
      label: 'L2 Distance',
      data: l2Data,
      borderColor: 'orange',
      fill: false
    }
  ]
};
window.onload = function() {
  new Chart(document.getElementById('evalChart').getContext('2d'), {
    type: 'line',
    data: data,
    options: {
      responsive: false,
      plugins: { legend: { position: 'top' } },
      scales: { y: { beginAtZero: true } }
    }
  });
};
</script>
<table>
<tr><th>Time</th><th>Status</th><th>Detail</th></tr>
{{range .}}
<tr{{if eq .Status "fail"}} style='background:#fdd'{{end}}>
<td>{{.Time}}</td><td>{{.Status}}</td><td>{{.Detail}}</td>
</tr>
{{end}}
</table>
</body>
</html>`

func handler(w http.ResponseWriter, r *http.Request) {
	entries, err := parseReport("cycle_report.log")
	if err != nil {
		http.Error(w, "cycle_report.log not found", 404)
		return
	}
	t := template.Must(template.New("dash").Parse(tmpl))
	t.Execute(w, entries)
}

func main() {
	http.HandleFunc("/", handler)
	fmt.Println("[Dashboard] http://localhost:8080 でサイクル履歴を閲覧できます")
	http.ListenAndServe(":8080", nil)
}
