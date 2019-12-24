# Datasheet for ADS7886: http://www.ti.com/lit/ds/symlink/ads7886.pdf
# In this hardware application, CS is generated by an "OR" from the detector's one-shot and the Pi's "HOLD" signal. In other words,
# ADC readings are triggered by either the detector or manually from the Pi. This script only uses the detector's trigger.

# Note that this signalling setup is pretty nonstandard. The ADC's CS is handled by the detector's latch. 
# Clock is only used to read out data and the sampling is handled by the peak detect and sample and hold.
# As a result, a slow clock can read data out quite slowly. This is easily bit-bangable as a result.
# Max toggle speed on GPIO in python is fairly low, far slower than the ADC's 20MHz limit, so no need to use delays after clock transitions before reading data.
# Send a clock signal at a reasonable-ish speed, wait for data. Read data manually. Repeat.

# Standards: Every method should end with SCLK high so no bits are accidentally skipped.

# Imports
import time # for delays (if needed)
import RPi.GPIO as GPIO # to use the GPIO
from datetime import datetime # for timestamps. 

# Setting constants for the analog readings.
vref = 3300 # Vref for ADC in mV
resolution = 12 # ADC resolution in bits (12 default)
offset = 0 # mV of voltage offset to apply to ADC output data
threshold = 200 # minimum event voltage to record in mV. Setting a threshold in hardware is strongly preferred, as the speed of the Pi is limited. If two events happen in close proximity, one of them may be missed.
sleepTime = 0.003 # Time to pause between measurements taken in seconds, 0.003 (3ms) default since the default deak detector time constant is 1ms.

# Preparing GPIO. 
clockPin = 31
sdoPin = 33
holdPin = 29

GPIO.setmode(GPIO.BOARD) # Pin numbers are based on the physical pin numbering.
GPIO.setwarnings(False)
GPIO.setup(holdPin, GPIO.OUT) # HOLD pin (can produce latch/CS on other boards).
GPIO.output(holdPin, GPIO.LOW) # This signal is currently unused. In this script the Pi only waits passively for data triggered by the detector. Rising edges on this line should trigger an instant measurement, but this hasn't been tested.
GPIO.setup(clockPin, GPIO.OUT) # SCLK (clock) pin
GPIO.setup(sdoPin, GPIO.IN, pull_up_down=GPIO.PUD_UP) # SDO pin. The first 4 bits after a conversion are all 0, so it's obvious where the data begins if this pin is pulled up (defaults to 1 when inactive).

ADC_file = open ("ADC_file.txt", "a+") # Open the ADC file in append mode. Creates the file if it does not exist.

# Methods Follow Below.

# Method accounts for the ADC startup behavior. The first sample read by the ADC after startup may be garbage data, so we need to ignore that.
def startADC(): 
    
    print('Starting ADC')

    waitForData() # run SCLK until SDO has data

    # Once data is detected, waitForData() will terminate. At that point toggle SCLK a bunch of times (at least 16) to clear the ADC register and the ADC is ready to go!
    for _i in range(20):
        GPIO.output(clockPin, GPIO.LOW)
        GPIO.output(clockPin, GPIO.HIGH)
        
    print('ADC started!')

# Method toggles SCLK until it detects the beginning of a data block (4 0's on SDO in a row). The next bit read after running this method will be the first valid data bit.
def waitForData():

    dataDetected = False # Data not detected yet.
    while not dataDetected: # This loop terminates if it gets its desired 4 bits of 0's on SDO. Otherwise it continues looping.
        GPIO.output(clockPin, GPIO.LOW) # Falling edge of SCLK
        GPIO.output(clockPin, GPIO.HIGH) # Since data is only clocked out on falling clock edges, it's safe to make the measurement after the rising one.

        if not GPIO.input(sdoPin): # If SDO goes low after a downward transition of SCLK, possible data has been detected.
            dataDetected = True             
            # At this point a single zero has been detected. A valid data block will begin with four zeros. 
            # So now read out three more bits. If any are not zeros, go back to waiting for data, because it's not a valid data block.
            for _i in range(3):
                GPIO.output(clockPin, GPIO.LOW)
                GPIO.output(clockPin, GPIO.HIGH)
                if GPIO.input(sdoPin):
                    dataDetected = False #if SDO goes high (1) at this point, the data is invalid. Back to the beginning of the while loop!
    
# Method waits for data then saves the ADC output (in mV) to a file.
def readADC():

    waitForData()

    # Now to read the next 12 bits and save them to an array.
    validDataList = list(range(resolution))
    for i in validDataList:
        GPIO.output(clockPin, GPIO.LOW)
        GPIO.output(clockPin, GPIO.HIGH)
        validDataList[i] = GPIO.input(sdoPin)

    # At this point I have an array of 12 data bits. This needs to be converted to a number.
    validData = 0
    for i in range(resolution): # Iterates over the list to produce base 10 number "validData"
        validData += validDataList[i]*(2**(resolution-i-1.0))

    # Convert number reading to a voltage in mV
    validData = (validData / (2.0 ** (resolution))) * vref + offset

    # Generate timestamp and save data to file.
    dt_string=datetime.now().strftime("%d %m %Y %H:%M:%S:%f")
    
    
    if (validData > threshold): # set a software threshold for values printed to terminal
        print(str(validData)+" mV")
        ADC_file.write("%s %f\n" % (dt_string, validData))

# Main method. Running this alone should detect all ADC inputs and save them to the file.
def main():

    startADC() # Discard the first ADC reading

    try:
        while True: # Record ADC readings until program is stopped.
            readADC()
            time.sleep(sleepTime) 
            # print ("Slept " + str(sleepTime) + " seconds...")
    except:
		ADC_file.write("%s %f\n" % (dt_string, validData))
        ADC_file.close()
        print("Done")
        
# Actually run the thing

main()