import signal
from datetime import datetime as dt
from datetime import timedelta as td
import socket
import sys
import struct
import time
from Crypto.Cipher import Salsa20

# ansi prefix
pref = "\033["

# ports for send and receive data
SendPort = 33739
ReceivePort = 33740

# ctrl-c handler
def handler(signum, frame):
	sys.stdout.write(f'{pref}?1049l')	# revert buffer
	sys.stdout.write(f'{pref}?25h')		# restore cursor
	sys.stdout.flush()
	exit(1)

# handle ctrl-c
signal.signal(signal.SIGINT, handler)

sys.stdout.write(f'{pref}?1049h')	# alt buffer
sys.stdout.write(f'{pref}?25l')		# hide cursor
sys.stdout.flush()

# get ip address from command line
if len(sys.argv) == 2:
    ip = sys.argv[1]
else:
    print('Run like : python3 gt7telemetry.py <playstation-ip>')
    exit(1)

# Create a UDP socket and bind it
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(('0.0.0.0', ReceivePort))
s.settimeout(10)

# data stream decoding
def salsa20_dec(dat):
	KEY = b'Simulator Interface Packet GT7 ver 0.0'
	# Seed IV is always located here
	oiv = dat[0x40:0x44]
	iv1 = int.from_bytes(oiv, byteorder='little')
	# Updated to use correct magic number for GT7
	iv2 = iv1 ^ 0xDEADBEEF
	IV = bytearray()
	IV.extend(iv2.to_bytes(4, 'little'))
	IV.extend(iv1.to_bytes(4, 'little'))
	
	cipher = Salsa20.new(key=KEY[0:32], nonce=bytes(IV))
	ddata = cipher.decrypt(dat)
	
	magic = int.from_bytes(ddata[0:4], byteorder='little')
	if magic != 0x47375330:
		return bytearray(b'')
	return ddata

# send heartbeat
def send_hb(s):
	send_data = 'B'
	s.sendto(send_data.encode('utf-8'), (ip, SendPort))

# generic print function
def printAt(str, row=1, column=1, bold=0, underline=0, reverse=0):
	sys.stdout.write('{}{};{}H'.format(pref, row, column))
	if reverse:
		sys.stdout.write('{}7m'.format(pref))
	if bold:
		sys.stdout.write('{}1m'.format(pref))
	if underline:
		sys.stdout.write('{}4m'.format(pref))
	if not bold and not underline and not reverse:
		sys.stdout.write('{}0m'.format(pref))
	sys.stdout.write(str)

def secondsToLaptime(seconds):
	remaining = seconds
	minutes = seconds // 60
	remaining = seconds % 60
	return '{:01.0f}:{:06.3f}'.format(minutes, remaining)

# Auto-scaling for acceleration bar charts - independent for each axis
accelSwayMax = 0.0
accelSwayMin = 0.0
accelHeaveMax = 0.0
accelHeaveMin = 0.0
accelSurgeMax = 0.0
accelSurgeMin = 0.0

def percentBarChart(value, barWidth=20):
	"""Create an ASCII bar chart for percentage values (0-100%)"""
	# Normalize to 0-1 range
	normalized = max(0.0, min(1.0, value / 100.0))
	
	# Calculate number of filled bars
	bars = int(normalized * barWidth)
	
	# Create the bar chart
	chart = '█' * bars + '░' * (barWidth - bars)
	
	return chart

def accelBarChart(value, axis, barWidth=20):
	"""Create an ASCII bar chart for acceleration values with independent auto-scaling per axis"""
	global accelSwayMax, accelSwayMin, accelHeaveMax, accelHeaveMin, accelSurgeMax, accelSurgeMin
	
	# Select the appropriate min/max based on axis
	if axis == 'sway':
		if value > accelSwayMax:
			accelSwayMax = value
		if value < accelSwayMin:
			accelSwayMin = value
		scale = max(abs(accelSwayMax), abs(accelSwayMin))
	elif axis == 'heave':
		if value > accelHeaveMax:
			accelHeaveMax = value
		if value < accelHeaveMin:
			accelHeaveMin = value
		scale = max(abs(accelHeaveMax), abs(accelHeaveMin))
	elif axis == 'surge':
		if value > accelSurgeMax:
			accelSurgeMax = value
		if value < accelSurgeMin:
			accelSurgeMin = value
		scale = max(abs(accelSurgeMax), abs(accelSurgeMin))
	else:
		scale = 0.1
	
	if scale == 0.0:
		scale = 0.1  # Avoid division by zero, use minimal scale
	
	# Normalize value to -1.0 to 1.0 range based on current scale
	normalized = max(-1.0, min(1.0, value / scale))
	
	# Calculate bar position (center is at barWidth/2)
	center = barWidth // 2
	if normalized >= 0:
		# Positive value - bar extends right from center
		bars = int(normalized * center)
		chart = ' ' * center + '|' + '█' * bars + ' ' * (center - bars)
	else:
		# Negative value - bar extends left from center
		bars = int(abs(normalized) * center)
		chart = ' ' * (center - bars) + '█' * bars + '|' + ' ' * center
	
	return chart



# start by sending heartbeat
send_hb(s)

printAt('GT7 Telemetry Display 0.7 (ctrl-c to quit)', 1, 1, bold=1)
printAt('Packet ID:', 1, 73)
printAt('Pkt Len:      bytes', 2, 73)
printAt('RX Rate:      Hz', 3, 73)

printAt('{:<92}'.format('Current Track Data'), 3, 1, reverse=1, bold=1)
printAt('Time on track:', 3, 41, reverse=1)
printAt('Laps:    /', 5, 1)
printAt('Position:   /', 5, 21)
printAt('Best Lap Time:', 7, 1)
printAt('Current Lap Time: ', 7, 31)
printAt('Last Lap Time:', 8, 1)

printAt('{:<92}'.format('Current Car Data'), 10, 1, reverse=1, bold=1)
printAt('Car ID:', 10, 41, reverse=1)
printAt('Throttle:    %', 12, 1)
printAt('RPM:        rpm', 12, 21)
printAt('Speed:        mph', 12, 41)
printAt('Brake:       %', 13, 1)
printAt('Gear:   ( )', 13, 21)
printAt('Boost:        kPa', 13, 41)
printAt('Rev Warning       rpm', 12, 71)
printAt('Rev Limiter       rpm', 13, 71)
printAt('Max:', 14, 21)
printAt('Est. Speed        kph', 14, 71)

printAt('Clutch:       /', 15, 1)
printAt('RPM After Clutch:        rpm', 15, 31)

printAt('Oil Temperature:       °C', 17, 1)
printAt('Water Temperature:       °C', 17, 31)
printAt('Oil Pressure:          bar', 18, 1)
printAt('Body/Ride Height:        mm', 18, 31)

printAt('Gearing', 20, 1, underline=1)
printAt('1st:', 21, 1)
printAt('2nd:', 22, 1)
printAt('3rd:', 23, 1)
printAt('4th:', 24, 1)
printAt('5th:', 25, 1)
printAt('6th:', 26, 1)
printAt('7th:', 27, 1)
printAt('8th:', 28, 1)
printAt('???:', 30, 1)

printAt('Positioning (m)', 20, 21, underline=1)
printAt('X:', 21, 21)
printAt('Y:', 22, 21)
printAt('Z:', 23, 21)

printAt('Velocity (m/s)', 20, 41, underline=1)
printAt('X:', 21, 41)
printAt('Y:', 22, 41)
printAt('Z:', 23, 41)

printAt('Rotation', 25, 21, underline=1)
printAt('P:', 26, 21)
printAt('Y:', 27, 21)
printAt('R:', 28, 21)

printAt('Angular (r/s)', 25, 41, underline=1)
printAt('X:', 26, 41)
printAt('Y:', 27, 41)
printAt('Z:', 28, 41)

printAt('Accel (m/s²)', 20, 61, underline=1)
printAt('Sway:', 21, 61)
printAt('Heave:', 22, 61)
printAt('Surge:', 23, 61)

printAt('N/S:', 30, 21)

sys.stdout.flush()

prevlap = -1
pktid = 0
pknt = 0
dt_start = dt.now()  # Initialize lap time tracking
# Framerate tracking
last_frame_time = time.time()
frame_count = 0
framerate = 0.0
framerate_update_interval = 0.5  # Update framerate every 0.5 seconds

while True:
	try:
		data, address = s.recvfrom(4096)
		pknt = pknt + 1
		
		# Calculate framerate
		current_time = time.time()
		frame_count += 1
		time_elapsed = current_time - last_frame_time
		
		if time_elapsed >= framerate_update_interval:
			framerate = frame_count / time_elapsed
			frame_count = 0
			last_frame_time = current_time
			printAt('{:6.2f}'.format(framerate), 3, 82)
		
		# Display packet length
		printAt('{:4d}'.format(len(data)), 2, 82)
		
		ddata = salsa20_dec(data)
		if len(ddata) > 0:
			# Extract and display packet ID immediately, even if out of order
			raw_pktid = struct.unpack('i', ddata[0x70:0x70+4])[0]
			printAt('{:>10}'.format(raw_pktid), 1, 83)						# packet id
			pktid = raw_pktid

			bstlap = struct.unpack('i', ddata[0x78:0x78+4])[0]
			lstlap = struct.unpack('i', ddata[0x7C:0x7C+4])[0]
			curlap = struct.unpack('h', ddata[0x74:0x74+2])[0]
			if curlap > 0:
				dt_now = dt.now()
				if curlap != prevlap:
					prevlap = curlap
					dt_start = dt_now
				curLapTime = dt_now - dt_start
				printAt('{:>9}'.format(secondsToLaptime(curLapTime.total_seconds())), 7, 49)
			else:
				curLapTime = 0
				printAt('{:>9}'.format(''), 7, 49)
					
			cgear = struct.unpack('B', ddata[0x90:0x90+1])[0] & 0b00001111
			sgear = struct.unpack('B', ddata[0x90:0x90+1])[0] >> 4
			if cgear < 1:
				cgear = 'R'
			if sgear > 14:
				sgear = '–'

			fuelCapacity = struct.unpack('f', ddata[0x48:0x48+4])[0]
			isEV = False if fuelCapacity > 0 else True
			if isEV:
				printAt('Charge:', 14, 1)
				printAt('{:3.0f} kWh'.format(struct.unpack('f', ddata[0x44:0x44+4])[0]), 14, 11)		# charge remaining
				printAt('??? kWh'.format(struct.unpack('f', ddata[0x48:0x48+4])[0]), 14, 29)			# max battery capacity
			else:
				printAt('Fuel:  ', 14, 1)
				printAt('{:3.0f} lit'.format(struct.unpack('f', ddata[0x44:0x44+4])[0]), 14, 11)		# fuel
				printAt('{:3.0f} lit'.format(struct.unpack('f', ddata[0x48:0x48+4])[0]), 14, 29)		# max fuel

			boost = struct.unpack('f', ddata[0x50:0x50+4])[0] - 1
			hasTurbo = True if boost > -1 else False


			tyreDiamFL = struct.unpack('f', ddata[0xB4:0xB4+4])[0]
			tyreDiamFR = struct.unpack('f', ddata[0xB8:0xB8+4])[0]
			tyreDiamRL = struct.unpack('f', ddata[0xBC:0xBC+4])[0]
			tyreDiamRR = struct.unpack('f', ddata[0xC0:0xC0+4])[0]

			tyreSpeedFL = abs(2.23694 * tyreDiamFL * struct.unpack('f', ddata[0xA4:0xA4+4])[0])
			tyreSpeedFR = abs(2.23694 * tyreDiamFR * struct.unpack('f', ddata[0xA8:0xA8+4])[0])
			tyreSpeedRL = abs(2.23694 * tyreDiamRL * struct.unpack('f', ddata[0xAC:0xAC+4])[0])
			tyreSpeedRR = abs(2.23694 * tyreDiamRR * struct.unpack('f', ddata[0xB0:0xB0+4])[0])

			carSpeed = 2.23694 * struct.unpack('f', ddata[0x4C:0x4C+4])[0]  # Convert m/s to mph

			if carSpeed > 0:
				tyreSlipRatioFL = '{:6.2f}'.format(tyreSpeedFL / carSpeed)
				tyreSlipRatioFR = '{:6.2f}'.format(tyreSpeedFR / carSpeed)
				tyreSlipRatioRL = '{:6.2f}'.format(tyreSpeedRL / carSpeed)
				tyreSlipRatioRR = '{:6.2f}'.format(tyreSpeedRR / carSpeed)
			else:
				tyreSlipRatioFL = '  –  '
				tyreSlipRatioFR = '  –  '
				tyreSlipRatioRL = '  -  '
				tyreSlipRatioRR = '  –  '

			printAt('{:>8}'.format(str(td(seconds=round(struct.unpack('i', ddata[0x80:0x80+4])[0] / 1000)))), 3, 56, reverse=1)	# time of day on track

			printAt('{:3.0f}'.format(curlap), 5, 7)															# current lap
			printAt('{:3.0f}'.format(struct.unpack('h', ddata[0x76:0x76+2])[0]), 5, 11)						# total laps

			printAt('{:2.0f}'.format(struct.unpack('h', ddata[0x84:0x84+2])[0]), 5, 31)						# current position
			printAt('{:2.0f}'.format(struct.unpack('h', ddata[0x86:0x86+2])[0]), 5, 34)						# total positions

			if bstlap != -1:
				printAt('{:>9}'.format(secondsToLaptime(bstlap / 1000)), 7, 16)		# best lap time
			else:
				printAt('{:>9}'.format(''), 7, 16)
			if lstlap != -1:
				printAt('{:>9}'.format(secondsToLaptime(lstlap / 1000)), 8, 16)		# last lap time
			else:
				printAt('{:>9}'.format(''), 8, 16)

			printAt('{:5.0f}'.format(struct.unpack('i', ddata[0x124:0x124+4])[0]), 10, 48, reverse=1)		# car id

			throttle = struct.unpack('B', ddata[0x91:0x91+1])[0] / 2.55
			brake = struct.unpack('B', ddata[0x92:0x92+1])[0] / 2.55
			
			printAt('{:3.0f}'.format(throttle), 12, 11)														# throttle
			printAt(percentBarChart(throttle, 10), 12, 61)													# throttle bar chart
			printAt('{:7.0f}'.format(struct.unpack('f', ddata[0x3C:0x3C+4])[0]), 12, 25)					# rpm
			printAt('{:7.1f}'.format(carSpeed), 12, 47)														# speed kph
			printAt('{:5.0f}'.format(struct.unpack('H', ddata[0x88:0x88+2])[0]), 12, 83)					# rpm rev warning

			printAt('{:3.0f}'.format(brake), 13, 11)														# brake
			printAt(percentBarChart(brake, 10), 13, 61)														# brake bar chart
			printAt('{}'.format(cgear), 13, 27)																# actual gear
			printAt('{}'.format(sgear), 13, 30)																# suggested gear

			if hasTurbo:
				printAt('{:7.2f}'.format(struct.unpack('f', ddata[0x50:0x50+4])[0] - 1), 13, 47)			# boost
			else:
				printAt('{:>7}'.format('–'), 13, 47)														# no turbo

			printAt('{:5.0f}'.format(struct.unpack('H', ddata[0x8A:0x8A+2])[0]), 13, 83)					# rpm rev limiter

			printAt('{:5.0f}'.format(struct.unpack('h', ddata[0x8C:0x8C+2])[0]), 14, 83)					# estimated top speed

			printAt('{:5.3f}'.format(struct.unpack('f', ddata[0xF4:0xF4+4])[0]), 15, 9)						# clutch
			printAt('{:5.3f}'.format(struct.unpack('f', ddata[0xF8:0xF8+4])[0]), 15, 17)					# clutch engaged
			printAt('{:7.0f}'.format(struct.unpack('f', ddata[0xFC:0xFC+4])[0]), 15, 48)					# rpm after clutch

			printAt('{:6.1f}'.format(struct.unpack('f', ddata[0x5C:0x5C+4])[0]), 17, 17)					# oil temp
			printAt('{:6.1f}'.format(struct.unpack('f', ddata[0x58:0x58+4])[0]), 17, 49)					# water temp

			printAt('{:6.2f}'.format(struct.unpack('f', ddata[0x54:0x54+4])[0]), 18, 17)					# oil pressure
			printAt('{:6.0f}'.format(1000 * struct.unpack('f', ddata[0x38:0x38+4])[0]), 18, 49)				# ride height

			printAt('{:7.3f}'.format(struct.unpack('f', ddata[0x104:0x104+4])[0]), 21, 5)					# 1st gear
			printAt('{:7.3f}'.format(struct.unpack('f', ddata[0x108:0x108+4])[0]), 22, 5)					# 2nd gear
			printAt('{:7.3f}'.format(struct.unpack('f', ddata[0x10C:0x10C+4])[0]), 23, 5)					# 3rd gear
			printAt('{:7.3f}'.format(struct.unpack('f', ddata[0x110:0x110+4])[0]), 24, 5)					# 4th gear
			printAt('{:7.3f}'.format(struct.unpack('f', ddata[0x114:0x114+4])[0]), 25, 5)					# 5th gear
			printAt('{:7.3f}'.format(struct.unpack('f', ddata[0x118:0x118+4])[0]), 26, 5)					# 6th gear
			printAt('{:7.3f}'.format(struct.unpack('f', ddata[0x11C:0x11C+4])[0]), 27, 5)					# 7th gear
			printAt('{:7.3f}'.format(struct.unpack('f', ddata[0x120:0x120+4])[0]), 28, 5)					# 8th gear

			printAt('{:7.3f}'.format(struct.unpack('f', ddata[0x100:0x100+4])[0]), 30, 5)					# ??? gear

			printAt('{:11.4f}'.format(struct.unpack('f', ddata[0x04:0x04+4])[0]), 21, 23)					# pos X
			printAt('{:11.4f}'.format(struct.unpack('f', ddata[0x08:0x08+4])[0]), 22, 23)					# pos Y
			printAt('{:11.4f}'.format(struct.unpack('f', ddata[0x0C:0x0C+4])[0]), 23, 23)					# pos Z

			printAt('{:11.4f}'.format(struct.unpack('f', ddata[0x10:0x10+4])[0]), 21, 43)					# velocity X
			printAt('{:11.4f}'.format(struct.unpack('f', ddata[0x14:0x14+4])[0]), 22, 43)					# velocity Y
			printAt('{:11.4f}'.format(struct.unpack('f', ddata[0x18:0x18+4])[0]), 23, 43)					# velocity Z

			printAt('{:9.4f}'.format(struct.unpack('f', ddata[0x1C:0x1C+4])[0]), 26, 23)					# rot Pitch
			printAt('{:9.4f}'.format(struct.unpack('f', ddata[0x20:0x20+4])[0]), 27, 23)					# rot Yaw
			printAt('{:9.4f}'.format(struct.unpack('f', ddata[0x24:0x24+4])[0]), 28, 23)					# rot Roll

			printAt('{:9.4f}'.format(struct.unpack('f', ddata[0x2C:0x2C+4])[0]), 26, 43)					# angular velocity X
			printAt('{:9.4f}'.format(struct.unpack('f', ddata[0x30:0x30+4])[0]), 27, 43)					# angular velocity Y
			printAt('{:9.4f}'.format(struct.unpack('f', ddata[0x34:0x34+4])[0]), 28, 43)					# angular velocity Z

			# Packet B fields (316 bytes) - acceleration data at end of packet
			# wheelRotation at 0x128 (296)
			# UNKNOWNFLOAT10 at 0x12C (300)
			# sway (X axis accel) at 0x130 (304)
			# heave (Y axis accel) at 0x134 (308)
			# surge (Z axis accel) at 0x138 (312)
			accelSway = struct.unpack('f', ddata[0x130:0x130+4])[0]
			accelHeave = struct.unpack('f', ddata[0x134:0x134+4])[0]
			accelSurge = struct.unpack('f', ddata[0x138:0x138+4])[0]
			
			printAt('{:9.4f}'.format(accelSway), 21, 67)														# accel Sway (lateral X)
			printAt(accelBarChart(accelSway, 'sway'), 21, 77)													# accel Sway bar chart
			printAt('{:9.4f}'.format(accelHeave), 22, 67)														# accel Heave (vertical Y)
			printAt(accelBarChart(accelHeave, 'heave'), 22, 77)													# accel Heave bar chart
			printAt('{:9.4f}'.format(accelSurge), 23, 67)														# accel Surge (longitudinal Z)
			printAt(accelBarChart(accelSurge, 'surge'), 23, 77)													# accel Surge bar chart

			printAt('{:7.4f}'.format(struct.unpack('f', ddata[0x28:0x28+4])[0]), 30, 25)					# rot ???

		if pknt > 100:
			send_hb(s)
			pknt = 0
	except Exception as e:
		printAt('Exception: {}'.format(e), 41, 1, reverse=1)
		send_hb(s)
		pknt = 0
		pass

	sys.stdout.flush()
