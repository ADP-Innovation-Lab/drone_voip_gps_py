import serial
import json
import re
import time

# Function to parse NMEA message and extract latitude and longitude
def parse_nmea_sentence(nmea_sentence):
    match = re.match(r'^\$GPGGA,(.*),(.*),(.*),(.*),(.*),(.*),.*$', nmea_sentence)
    if match:
        time, lat, lat_dir, lon, lon_dir, fix, *_ = match.groups()
        if fix == '0' or lat == '' or lon == '':  # No GPS fix
            return 0.0, 0.0
        lat = float(lat[:2]) + float(lat[2:]) / 60.0
        if lat_dir == 'S':
            lat = -lat
        lon = float(lon[:3]) + float(lon[3:]) / 60.0
        if lon_dir == 'W':
            lon = -lon
        return lat, lon
    return 0.0, 0.0

# Configuration
port = '/dev/ttyUSB2'
baudrate = 115200
drone_id = "drone101"  # Replace with actual drone ID
battery_status = "85%"  # Replace with actual battery status if available

def open_serial_port(port, baudrate):
    while True:
        try:
            ser = serial.Serial(port, baudrate, timeout=10)
            print("Serial port opened successfully.")
            return ser
        except serial.SerialException:
            print("Failed to open serial port. Retrying in 1 minute...")
            time.sleep(60)

def read_from_port(ser):
    while True:
        try:
            line = ser.readline().decode('ascii', errors='replace').strip()
            if len(line) < 10:
                print("Timeout error: Received less than 10 characters.")
                continue
            if line.startswith('$GPGGA'):
                return line
        except serial.SerialTimeoutException:
            print("Timeout error: No data received within 10 seconds.")
            continue

def main():
    ser = open_serial_port(port, baudrate)
    try:
        while True:
            line = read_from_port(ser)
            lat, lon = parse_nmea_sentence(line)
            msg = {
                "drone_id": drone_id,
                "lat": lat,
                "long": lon,
                "bat": battery_status
            }
            with open('device.json', 'w') as f:
                json.dump(msg, f)
            print(f"Location info saved to device.json: {msg}")
    finally:
        ser.close()

if __name__ == "__main__":
    main()
