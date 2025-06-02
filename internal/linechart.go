package internal

import (
	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/canvas"
	"fyne.io/fyne/v2/container"
	"image/color"
)

// LineChart is a simple 2D line chart for Fyne
func LineChart(title string, xs, ys []float64, lineColor color.Color) fyne.CanvasObject {
	w, h := 600.0, 200.0
	minY, maxY := ys[0], ys[0]
	for _, v := range ys {
		if v < minY { minY = v }
		if v > maxY { maxY = v }
	}
	if maxY == minY { maxY += 1 }
	points := []fyne.CanvasObject{}
	prevX, prevY := 0.0, 0.0
	for i, y := range ys {
		x := w * float64(i) / float64(len(ys)-1)
		yNorm := (y - minY) / (maxY - minY)
		yPix := h - yNorm*h
		circ := canvas.NewCircle(lineColor)
		circ.Resize(fyne.NewSize(4,4))
		circ.Move(fyne.NewPos(float32(x-2), float32(yPix-2)))
		points = append(points, circ)
		if i > 0 {
			line := canvas.NewLine(lineColor)
			line.StrokeWidth = 2
			line.Position1 = fyne.NewPos(float32(prevX), float32(prevY))
			line.Position2 = fyne.NewPos(float32(x), float32(yPix))
			points = append(points, line)
		}
		prevX, prevY = x, yPix
	}
	return container.NewVBox(
		canvas.NewText(title, lineColor),
		container.NewWithoutLayout(points...),
	)
}
