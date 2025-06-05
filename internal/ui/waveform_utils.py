import numpy as np
import matplotlib.pyplot as plt
import soundfile as sf
import io
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class WaveformCanvas(FigureCanvas):
    def __init__(self, audio_path, parent=None, width=4, height=1.5, dpi=100, title=''):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)
        self.setParent(parent)
        self.plot_waveform(audio_path, title)

    def plot_waveform(self, audio_path, title=''):
        self.axes.clear()
        data, samplerate = sf.read(audio_path)
        if data.ndim > 1:
            data = data.mean(axis=1)
        t = np.linspace(0, len(data) / samplerate, num=len(data))
        self.axes.plot(t, data, color='blue')
        self.axes.set_xlabel('Time [s]')
        self.axes.set_ylabel('Amplitude')
        self.axes.set_title(title)
        self.axes.set_xlim([0, t[-1]])
        self.draw()
