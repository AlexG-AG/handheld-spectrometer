import matplotlib.pyplot as plt
import numpy as np
import datetime as dt
import os
import math
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
    avg_intensities = np.average(intensities, axis=0) # Average all collected scans

    fig, ax = plt.subplots()
    ax.plot(wavelengths, avg_intensities, color="blue", linestyle="-", label="Normal")
    plt.show()
    plt.close()

    spectrum = np.array([wavelengths, avg_intensities])

    return spec, spectrum

def calibrate_spectrum(spectrometer, spectrum):
    # Need to load a calibration (based on the spectrometer being used?) and scale the spectrum accordingly
    # Calibration file and spectrum wavelengths mat not necessarily be the same: USB4000 calibration using OceanView only covers up to 906nm, but the script measures up to 940nm. This needs to be handled, hopefully regardless of spectrometer.
    spectrometer_name = str(spectrometer).split(":")[0].split(" ")[1]

    calibration_path = os.path.join(".", "calibrations", spectrometer_name)
    for file in os.listdir(calibration_path):
        if file.endswith(".cal"):
            filepath = os.path.join(calibration_path, file)
            break

    cald_spectrum = [[], []]

    with open(filepath, "r") as f:
        #parse calibration file
        cal_data = f.readlines()[9:]
        for i in range(0, len(cal_data)):
            wavelength = cal_data[i].split('\t')[0]
            intensity_scaling = cal_data[i].split('\t')[1]
            if math.isclose(spectrum[0][i], float(wavelength)):
                cald_spectrum[0].append(spectrum[0][i])
                cald_spectrum[1].append(spectrum[1][i]*float(intensity_scaling))
        
    f.close()

    return cald_spectrum

def integrate_spectrum(spectrum):

    wavelengths = spectrum[0]
    intensities = spectrum[1]

    # Calculate the absolute difference between each array entry, then return the index of the smallest difference (The closest match)
    point1 = np.abs(np.subtract(wavelengths, 350)).argmin()
    point2 = np.abs(np.subtract(wavelengths, 420)).argmin()
    point3 = np.abs(np.subtract(wavelengths, 550)).argmin()

    violet_wavelengths = wavelengths[point1:(point2 + 1)]
    blue_wavelengths = wavelengths[point2:(point3 + 1)]
    total_wavelengths = wavelengths[point1:(point3 + 1)]
    
    violet_intensities = intensities[point1:(point2 + 1)]
    blue_intensities = intensities[point2:(point3 + 1)]
    total_intensities = intensities[point1:(point3 + 1)]

    violet_power = np.trapezoid(y=violet_intensities, x=violet_wavelengths)
    blue_power = np.trapezoid(y=blue_intensities, x=blue_wavelengths)
    total_power = np.trapezoid(y=total_intensities, x=total_wavelengths)

    return violet_power, blue_power, total_power

def save_results(spectrometer, spectrum, violet_power, blue_power, total_power):
    # Need to fix os.path.join usage
    today = dt.date.today().strftime("%d-%m-%Y")
    foldername = os.path.join(".", "output", today)
    if os.path.exists(foldername) == False: 
        os.mkdir(foldername)

    filename = dt.datetime.now().strftime("%d-%m-%Y--%H-%M-%S.txt")
    filepath = os.path.join(foldername, filename)
    with open(filepath, "w") as f:
        f.write(f"{spectrometer}\n----------\n")
        f.write(f"350-420nm Power (mW): {violet_power}\n")
        f.write(f"420-550nm Power (mW): {blue_power}\n")
        f.write(f"350-550nm Power (mW): {total_power}\n")
        f.write(f"Spectrum:\n")
        for i in range(0, len(spectrum[0])):
            f.write(f"{spectrum[0][i]}\t{spectrum[1][i]}\n")

    f.close()

    return

def main():
    spectrometer, spectrum = get_spectrum(20000, 5)
    cald_spectrum = calibrate_spectrum(spectrometer, spectrum)
    violet_power, blue_power, total_power = integrate_spectrum(cald_spectrum)
    save_results(spectrometer, cald_spectrum, violet_power, blue_power, total_power)
    
if __name__ == "__main__":
    main()