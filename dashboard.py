import signal
import sys
import socket
import struct
import json
from datetime import datetime as dt
from datetime import timedelta as td
from flask import Flask, render_template
from flask_socketio import SocketIO
from threading import Thread
from Crypto.Cipher import Salsa20
from collections import deque

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Ports for send and receive data
SendPort = 33739
ReceivePort = 33740

# Global variables
telemetry_data = {
    'throttle': 0,
    'brake': 0,
    'speed': 0,
    'rpm': 0,
    'gear': 'N',
    'position_x': 0,
    'position_y': 0,
    'velocity_x': 0,
    'velocity_y': 0,
    'lap_time': '0:00.000',
    'current_lap': 0,
    'position_history': []
}

position_history = deque()  # Keep entire position history
ip = None
udp_socket = None

def salsa20_dec(dat):
    KEY = b'Simulator Interface Packet GT7 ver 0.0'
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

def send_hb(s):
    send_data = 'B'
    s.sendto(send_data.encode('utf-8'), (ip, SendPort))

def secondsToLaptime(seconds):
    remaining = seconds
    minutes = seconds // 60
    remaining = seconds % 60
    return '{:01.0f}:{:06.3f}'.format(minutes, remaining)

def telemetry_receiver():
    global telemetry_data, position_history, udp_socket
    
    prevlap = -1
    pktid = 0
    pknt = 0
    dt_start = dt.now()
    last_position_time = 0
    
    while True:
        try:
            data, address = udp_socket.recvfrom(4096)
            pknt = pknt + 1
            ddata = salsa20_dec(data)
            
            if len(ddata) > 0:
                pktid = struct.unpack('i', ddata[0x70:0x70+4])[0]
                
                # Extract telemetry data
                throttle = struct.unpack('B', ddata[0x91:0x91+1])[0] / 2.55
                brake = struct.unpack('B', ddata[0x92:0x92+1])[0] / 2.55
                speed = 2.237 * struct.unpack('f', ddata[0x4C:0x4C+4])[0]  # Convert to mph (m/s * 2.237)
                rpm = struct.unpack('f', ddata[0x3C:0x3C+4])[0]
                
                cgear = struct.unpack('B', ddata[0x90:0x90+1])[0] & 0b00001111
                if cgear < 1:
                    cgear = 'R'
                elif cgear == 0:
                    cgear = 'N'
                else:
                    cgear = str(cgear)
                
                position_x = struct.unpack('f', ddata[0x04:0x04+4])[0]
                position_y = struct.unpack('f', ddata[0x08:0x08+4])[0]
                position_z = struct.unpack('f', ddata[0x0C:0x0C+4])[0]
                velocity_x = struct.unpack('f', ddata[0x10:0x10+4])[0]
                velocity_y = struct.unpack('f', ddata[0x14:0x14+4])[0]
                velocity_z = struct.unpack('f', ddata[0x18:0x18+4])[0]
                
                # Extract angular velocity (rotation rates) from correct offsets
                # These represent rotation rates around each axis
                angular_vel_x = struct.unpack('f', ddata[0x2C:0x2C+4])[0]  # Roll rate
                angular_vel_y = struct.unpack('f', ddata[0x30:0x30+4])[0]  # Pitch rate  
                angular_vel_z = struct.unpack('f', ddata[0x34:0x34+4])[0]  # Yaw rate
                
                # Extract acceleration data (Packet B fields)
                # sway (X axis accel) at 0x130 (304)
                # heave (Y axis accel) at 0x134 (308)
                # surge (Z axis accel) at 0x138 (312)
                accel_sway = struct.unpack('f', ddata[0x130:0x130+4])[0] if len(ddata) >= 316 else 0.0
                accel_heave = struct.unpack('f', ddata[0x134:0x134+4])[0] if len(ddata) >= 316 else 0.0
                accel_surge = struct.unpack('f', ddata[0x138:0x138+4])[0] if len(ddata) >= 316 else 0.0
                
                curlap = struct.unpack('h', ddata[0x74:0x74+2])[0]
                
                # Calculate lap time and handle lap transitions
                if curlap > 0:
                    dt_now = dt.now()
                    # Clear position history when transitioning from lap 0 to lap 1 (race start/restart)
                    if curlap == 1 and prevlap != 1:
                        position_history.clear()
                        dt_start = dt_now
                    elif curlap != prevlap:
                        dt_start = dt_now
                    prevlap = curlap
                    curLapTime = dt_now - dt_start
                    lap_time = secondsToLaptime(curLapTime.total_seconds())
                else:
                    # When lap is 0, update prevlap to track it properly
                    lap_time = '0:00.000'
                    prevlap = curlap
                
                # Add to position history every 0.25 seconds, only when actively racing (lap > 0)
                import time
                current_time = time.time()
                if curlap > 0 and current_time - last_position_time >= 0.25:
                    position_history.append({'x': position_x, 'y': -position_z})
                    last_position_time = current_time
                
                # Update global telemetry data
                telemetry_data = {
                    'throttle': round(throttle, 1),
                    'brake': round(brake, 1),
                    'speed': round(speed, 1),
                    'rpm': round(rpm, 0),
                    'gear': cgear,
                    'position_x': round(position_x, 2),
                    'position_y': round(position_y, 2),
                    'position_z': round(position_z, 2),
                    'velocity_x': round(velocity_x, 2),
                    'velocity_y': round(velocity_y, 2),
                    'velocity_z': round(velocity_z, 2),
                    'angular_vel_x': round(angular_vel_x, 3),
                    'angular_vel_y': round(angular_vel_y, 3),
                    'angular_vel_z': round(angular_vel_z, 3),
                    'accel_sway': round(accel_sway, 3),
                    'accel_heave': round(accel_heave, 3),
                    'accel_surge': round(accel_surge, 3),
                    'lap_time': lap_time,
                    'current_lap': curlap,
                    'position_history': list(position_history)
                }
                
                # Emit data to connected clients
                socketio.emit('telemetry_update', telemetry_data)
            
            if pknt > 100:
                send_hb(udp_socket)
                pknt = 0
                
        except Exception as e:
            print(f'Error receiving telemetry: {e}')
            send_hb(udp_socket)
            pknt = 0

@app.route('/')
def index():
    import time
    response = app.make_response(render_template('dashboard.html', version=int(time.time())))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    socketio.emit('telemetry_update', telemetry_data)

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('clear_history')
def handle_clear_history():
    global position_history
    position_history.clear()
    print('Position history cleared by user')

def signal_handler(signum, frame):
    print('\nShutting down...')
    if udp_socket:
        udp_socket.close()
    sys.exit(0)

if __name__ == '__main__':
    import os
    signal.signal(signal.SIGINT, signal_handler)
    
    # Get IP address from command line
    if len(sys.argv) == 2:
        ip = sys.argv[1]
    else:
        print('Run like: python3 dashboard.py <playstation-ip>')
        sys.exit(1)
    
    # Only initialize UDP socket in the main reloader process (not the parent process)
    # WERKZEUG_RUN_MAIN is set by Flask's reloader in the actual worker process
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # Create UDP socket
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind(('0.0.0.0', ReceivePort))
        udp_socket.settimeout(10)
        
        # Send initial heartbeat
        send_hb(udp_socket)
        
        # Start telemetry receiver thread
        receiver_thread = Thread(target=telemetry_receiver, daemon=True)
        receiver_thread.start()
        
        print(f'GT7 Telemetry Dashboard starting...')
        print(f'Connected to PlayStation at {ip}')
        print(f'Open http://localhost:5001 in your browser')
    
    # Start Flask app
    socketio.run(app, host='0.0.0.0', port=5001, debug=True, use_reloader=True)
