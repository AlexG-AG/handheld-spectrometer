import matplotlib.pyplot as plt
import numpy as np
import seabreeze
seabreeze.use('pyseabreeze')
from seabreeze.spectrometers import Spectrometer

def get_spectrum(integtime, scans):
    intensities = []

    spec = Spectrometer.from_first_available()
    spec.integration_time_micros(integtime)
    wavelengths = spec.wavelengths()

    for i in range(0, scans):
        intensities.append(spec.intensities())

    print(intensities)
    avgintensities = np.average(intensities)

    fig, ax = plt.subplots()

    ax.plot(wavelengths, avgintensities, color="blue", linestyle="-", label="Normal")
    plt.show()
    plt.close()

def main():
    get_spectrum(20000, 5)