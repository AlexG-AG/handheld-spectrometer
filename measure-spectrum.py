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
        print(f"Integration time set to {integtime} microseconds")

    return integtime

def get_supported_corrections(spec_name):
    if spec_name == "USB4000":
        return True, False # The API throws an error and says the USB4000 does not support nonlinearlity correction... except it does?
    if spec_name == "SR6":
        return False, False

def get_spectrum(spectrometer=None, scans=1):

    wavelengths = spectrometer.wavelengths()
    intensities = []

    dark_supported, nonlin_supported = get_supported_corrections(spectrometer.model)

    for i in range(0, scans):
        intensities.append(spectrometer.intensities(correct_dark_counts=dark_supported, correct_nonlinearity=nonlin_supported))
    avg_intensities = np.mean(intensities, axis=0) # Average all collected scans

    """
    fig, ax = plt.subplots()
    ax.plot(wavelengths, avg_intensities, color="blue", linestyle="-", label="Normal")
    plt.show()
    plt.close()
    """

    spectrum = np.array([wavelengths, avg_intensities])

    return spectrum

def calculate_dl(cal_wavelengths):
    # Calculate dL, the wavelength spread (how many nanometers a given pixel represents)
    # First and last points in the spectrum may not be handled 100% correctly, but the difference this makes should be minor.

    dl = []

    for i in range(0, len(cal_wavelengths)): # Need to handle the first and last array elements separately
        if i == 0:
            dl.append(float(cal_wavelengths[i+1]) - float(cal_wavelengths[i])) # Handle first pixel
        elif i == len(cal_wavelengths) - 1:
            dl.append(float(cal_wavelengths[i]) - float(cal_wavelengths[i - 1])) # Handle last pixel
        else:
            dl.append((float(cal_wavelengths[i+1]) - float(cal_wavelengths[i-1]))/2)
    
    return dl

def calibrate_spectrum(spectrometer, integtime, background, spectrum):
    # Calibration file and spectrum wavelengths may not necessarily be the same: USB4000 calibration using OceanView only covers up to 906nm, but the script measures up to 940nm.
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
        cal_wavelengths = []
        cal_intensities = []

        for i in range(0, len(cal_data)):
            wavelength = cal_data[i].split('\t')[0]
            intensity_scaling = cal_data[i].split('\t')[1]

            cal_wavelengths.append(wavelength)
            cal_intensities.append(intensity_scaling)

        dl = calculate_dl(cal_wavelengths)

        for i in range(0, len(cal_data)):
            if math.isclose(spectrum[0][i], float(cal_wavelengths[i])):
                cald_spectrum[0].append(spectrum[0][i])
                spec_rad_flux = (spectrum[1][i]*float(cal_intensities[i]))/(integtime_seconds * dl[i] * 1000) # Convert to mW/nm
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
    spec_name = spectrometer.model
    today = dt.date.today().strftime("%d-%m-%Y")
    foldername = os.path.join(".", "output", today)
    if os.path.exists(foldername) == False: 
        os.mkdir(foldername)

    filename = dt.datetime.now().strftime(f"{spec_name}_%d-%m-%Y_%H-%M-%S.txt")
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

def integration_time_tool(spectrometer):
    # Could run the spectrum plot display on a separate thread for convenience
    integration_time = 3000000 # Start with a 3s integration time

    input("Turn on the LCU, then press Enter to begin:")

    while True:
        set_integration_time(spectrometer, integration_time)
        spectrum = get_spectrum(spectrometer)

        print(max(spectrum[1]))

        fig, ax = plt.subplots()
        ax.plot(spectrum[0], spectrum[1], color="blue", linestyle="-", label="Normal")
        ax.set_ylim(ymax=70000)
        ax.axhline(y=65535, color='k', linestyle='--')
        plt.show()
        ax.cla()
        plt.close()

        while True:
            selection = input("Please select an option below:\n[1] Integration time too high\n[2] Integration time too low\n[3] Finish with current integration time\n")

            if selection == "1":
                integration_time = int(integration_time*0.5) # Drop integration time by 50%
                break

            elif selection == "2":
                integration_time = int(integration_time*1.25) # Increase integration time by 25%
                break

            elif selection == "3":
                return integration_time
                
            else:
                print("Invalid input received, try again")

def calibrate_spectrometer(spectrometer, integtime, scans):
    # Implement procedure to calibrate the spectrometer using a known light source and generate a calibration file
    return

def main():
    integration_time = 100000
    scans_to_avg = 5

    print("Connecting to spectrometer...\n")
    spec = connect_spectrometer()
    print(f"Connected to spectrometer {spec}\n")

    while True:
        selection = input("---------------------------------\nSelect an option from the list below\n[0] Quit\n[1] Set Integration Time\n[2] Measure Spectrum\n[3] Calibrate Spectrometer\n")
        if selection == "0": # Quit program
            break

        elif selection == "1": # Set integration time
            while True:
                selection = input("---------------------------------\nIntegration time settings:\n[1] Integration time audjustment tool\n[2] Enter integration time manually\n[3] Go back\n")
                if selection == "1":
                    integration_time = integration_time_tool(spec)
                elif selection == "2":
                    manual_time = input("Enter the desired integration time in microseconds: ")
                    integration_time = set_integration_time(spec, int(manual_time))
                elif selection == "3":
                    break
                else:
                    print("Invalid input received, try again")

        elif selection == "2": # Measure spectrum
            input("Collect a background spectrum with the LCU off. Press Enter to proceed:")
            background = get_spectrum(spectrometer=spec, scans=scans_to_avg)
            input("Press Enter to proceed with LCU measurement:")
            spectrum = get_spectrum(spectrometer=spec, scans=scans_to_avg)
            cald_spectrum = calibrate_spectrum(spec, integration_time, background, spectrum)
            violet_power, blue_power, total_power = integrate_spectrum(cald_spectrum)
            save_results(spec, cald_spectrum, violet_power, blue_power, total_power)

        elif selection == "3": # Calibrate spectrometer
            calibrate_spectrometer()

        else:
            print("Invalid input received, try again")


if __name__ == "__main__":
    main()