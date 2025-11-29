# GT7 Telemetry Dashboard

A real-time web-based dashboard for Gran Turismo 7 telemetry data visualization.

## Features

- **Real-time Telemetry Plot**: Displays throttle, brake, speed, and RPM over time
- **2D Track Position Map**: Shows XY position with velocity vector arrow
- **Position History Trail**: Visualizes the car's path on the track
- **Lap Timer**: Real-time lap time display
- **Live Statistics**: Current lap, speed, and gear information

## Requirements

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Required packages:
- pycryptodome==3.19.0
- flask==3.0.0
- flask-socketio==5.3.5

## Usage

1. Make sure your PlayStation is on the same network and GT7 is running
2. Enable telemetry in GT7 settings
3. Run the dashboard with your PlayStation's IP address:

```bash
python3 dashboard.py <playstation-ip>
```

For example:
```bash
python3 dashboard.py 192.168.1.100
```

4. Open your web browser and navigate to:
```
http://localhost:5000
```

5. The dashboard will automatically connect and start displaying real-time telemetry data

## Dashboard Layout

### Top Section
- **Lap Time Clock**: Large yellow display showing current lap time
- **Status Indicators**: Current lap number, speed, and gear
- **Connection Status**: Green when connected, red when disconnected

### Left Plot - Vehicle Telemetry
- **Green Line**: Throttle position (%)
- **Red Line**: Brake position (%)
- **Cyan Line**: Vehicle speed (km/h)
- **Yellow Line**: Engine RPM (divided by 100 for scale)

### Right Plot - Track Position
- **Gray Line**: Historical track path (last 500 positions)
- **Red Dot**: Current vehicle position
- **Green Arrow**: Velocity vector showing direction and magnitude

## Technical Details

- The dashboard uses Flask for the web server
- WebSocket (Socket.IO) for real-time data streaming
- Plotly.js for interactive plots
- UDP port 33740 for receiving telemetry from GT7
- Updates position history with last 500 data points
- Telemetry plot shows last 100 time-series data points

## Troubleshooting

**Dashboard shows "Disconnected":**
- Verify GT7 is running and telemetry is enabled
- Check that the PlayStation IP address is correct
- Ensure both devices are on the same network
- Check firewall settings allow UDP port 33740

**Plots not updating:**
- Refresh the browser page
- Check the terminal for error messages
- Verify telemetry data is being received (check terminal output)

**Performance issues:**
- Close other browser tabs
- Reduce the maxDataPoints value in dashboard.html if needed
- Check network connection quality

## Notes

- The dashboard displays data in real-time as it's received from GT7
- Position history accumulates during the session
- Velocity arrows are scaled 5x for visibility
- RPM values are divided by 100 for better visualization alongside speed
