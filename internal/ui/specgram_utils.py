import numpy as np
import matplotlib.pyplot as plt
import soundfile as sf
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class SpecgramCanvas(FigureCanvas):
    def __init__(self, audio_path, parent=None, width=4, height=1.5, dpi=100, title=''):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)
        self.setParent(parent)
        self.plot_specgram(audio_path, title)

    def plot_specgram(self, audio_path, title=''):
        self.axes.clear()
        data, samplerate = sf.read(audio_path)
        if data.ndim > 1:
            data = data.mean(axis=1)
        self.axes.specgram(data, Fs=samplerate, NFFT=1024, noverlap=512, cmap='magma')
        self.axes.set_xlabel('Time [s]')
        self.axes.set_ylabel('Frequency [Hz]')
        self.axes.set_title(title)
        self.draw()
