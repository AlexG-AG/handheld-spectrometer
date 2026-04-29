import matplotlib.pyplot as plt
import numpy as np
import datetime as dt
import os
import math
import seabreeze
seabreeze.use('pyseabreeze')
from seabreeze.spectrometers import Spectrometer

def connect_spectrometer():
    spec = Spectrometer.from_first_available()
    return spec

def set_integration_time(spec, integtime):
    integ_time_limits = spec.integration_time_micros_limits
    if integtime < integ_time_limits[0] or integtime >= integ_time_limits[1]:
        print(f"Integration time outside of spectrometer limits, must be {integ_time_limits[0]} <= Int. Time < {integ_time_limits[1]}")
        return
    else:
        spec.integration_time_micros(integtime)
        print("Integration time set")

    return integtime

def get_spectrum(spectrometer=None, scans=1):

    wavelengths = spectrometer.wavelengths()
    intensities = []

    for i in range(0, scans):
        intensities.append(spectrometer.intensities(correct_dark_counts=True)) # The API throws an error and says the USB4000 does not support nonlinearlity correction... except it does?
    avg_intensities = np.mean(intensities, axis=0) # Average all collected scans

    fig, ax = plt.subplots()
    ax.plot(wavelengths, avg_intensities, color="blue", linestyle="-", label="Normal")
    plt.show()
    plt.close()

    spectrum = np.array([wavelengths, avg_intensities])

    return spectrum

def calibrate_spectrum(spectrometer, integtime, background, spectrum):
    # Need to load a calibration (based on the spectrometer being used?) and scale the spectrum accordingly
    # Calibration file and spectrum wavelengths mat not necessarily be the same: USB4000 calibration using OceanView only covers up to 906nm, but the script measures up to 940nm. This needs to be handled, hopefully regardless of spectrometer.
    spectrometer_name = spectrometer.model

    # Subtract background spectrum
    for i in range(0, len(background)):
        spectrum[1][i] -= background[1][i]

    calibration_path = os.path.join(".", "calibrations", spectrometer_name)
    for file in os.listdir(calibration_path):
        if file.endswith(".cal"):
            filepath = os.path.join(calibration_path, file)
            break

    cald_spectrum = [[], []]
    integtime_seconds = integtime/1000000
    
    with open(filepath, "r") as f:
        #parse calibration file
        cal_data = f.readlines()[9:]
        num_pixels = len(cal_data)
        bandpass = spectrum[0][-1] - spectrum[0][0]
        resolution = bandpass/num_pixels # The pixel dispersion for the spectrometer is not constant along all wavelengths, but I'm approximating it as constant for now.

        for i in range(0, len(cal_data)):
            wavelength = cal_data[i].split('\t')[0]
            intensity_scaling = cal_data[i].split('\t')[1]
            if math.isclose(spectrum[0][i], float(wavelength)):
                cald_spectrum[0].append(spectrum[0][i])
                spec_rad_flux = (spectrum[1][i]*float(intensity_scaling))/(integtime_seconds * resolution * 1000) # Convert to mW/nm
                cald_spectrum[1].append(spec_rad_flux)
        
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

def auto_integration_time(spectrometer):
    max_intensity = spectrometer.f.spectrometer.get_maximum_intensity()


    return spectrometer

def calibrate_spectrometer(spectrometer, integtime, scans):
    # Implement procedure to calibrate the spectrometer using a known light source and generate a calibration file
    return

def main():
    integration_time = 10000
    scans_to_avg = 5

    print("Connecting to spectrometer...\n")
    spec = connect_spectrometer()
    print(f"Connected to spectrometer {spec}\n")

    while True:
        selection = input("Select an option from the list below, [0] to quit:\n[1] Set Integration Time\n[2] Measure Spectrum\n[3] Calibrate Spectrometer\n")
        if selection == "0": # Quit program
            break

        if selection == "1": # Set integration time
            while True:
                selection = input("Integration time settings:\n[1] Automatically set integration time\n[2] Enter integration time manually\n[3] Go back\n")
                if selection == "1":
                    auto_integration_time(spec)
                    continue
                if selection == "2":
                    manual_time = input("Enter the desired integration time in microseconds:")
                    integration_time = set_integration_time(spec, int(manual_time))
                    continue
                if selection == "3":
                    break
                else:
                    print("Invalid input received, try again")
            continue

        if selection == "2": # Measure spectrum
            input("Collect a background spectrum with the LCU off. Press Enter to proceed:")
            background = get_spectrum(spectrometer=spec, scans=scans_to_avg)
            input("Press Enter to proceed with LCU measurement:")
            spectrum = get_spectrum(spectrometer=spec, scans=scans_to_avg)
            cald_spectrum = calibrate_spectrum(spec, integration_time, background, spectrum)
            violet_power, blue_power, total_power = integrate_spectrum(cald_spectrum)
            save_results(spec, cald_spectrum, violet_power, blue_power, total_power)
            continue

        if selection == "3": # Calibrate spectrometer
            calibrate_spectrometer()
            continue

        else:
            print("Invalid input received, try again")


if __name__ == "__main__":
    main()