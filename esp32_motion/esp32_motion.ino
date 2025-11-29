/*
  GT7 Telemetry Motion Data Reader for ESP32-C3 Super Mini
  
  Connects to WiFi, receives GT7 telemetry packets from PlayStation,
  decrypts using Salsa20, and outputs sway, heave, and surge acceleration.
*/

#include <WiFi.h>
#include <WiFiUdp.h>
#include <ESPping.h>

// WiFi credentials
const char* ssid = "MatrixGaming";
const char* password = "the dog barks at midnight";

// GT7 telemetry settings
const uint16_t ReceivePort = 33740;
const uint16_t SendPort = 33739;
const char* ps4IP = "192.168.10.209";

// UDP object
WiFiUDP udp;

// LED pin for ESP32-C3 Super Mini (typically GPIO8)
#define LED_BUILTIN 8

// Salsa20 decryption key
const uint8_t SALSA20_KEY[] = "Simulator Interface Packet GT7 ver 0.0";

// Buffer for incoming packets
uint8_t packetBuffer[512];

// Salsa20 state
void salsa20_quarter_round(uint32_t *x, int a, int b, int c, int d) {
  x[b] ^= ((x[a] + x[d]) << 7) | ((x[a] + x[d]) >> (32 - 7));
  x[c] ^= ((x[b] + x[a]) << 9) | ((x[b] + x[a]) >> (32 - 9));
  x[d] ^= ((x[c] + x[b]) << 13) | ((x[c] + x[b]) >> (32 - 13));
  x[a] ^= ((x[d] + x[c]) << 18) | ((x[d] + x[c]) >> (32 - 18));
}

void salsa20_block(uint32_t out[16], uint32_t const in[16]) {
  uint32_t x[16];
  for (int i = 0; i < 16; i++) x[i] = in[i];

  for (int i = 0; i < 10; i++) {
    // Column rounds
    salsa20_quarter_round(x, 0, 4, 8, 12);
    salsa20_quarter_round(x, 5, 9, 13, 1);
    salsa20_quarter_round(x, 10, 14, 2, 6);
    salsa20_quarter_round(x, 15, 3, 7, 11);
    // Row rounds
    salsa20_quarter_round(x, 0, 1, 2, 3);
    salsa20_quarter_round(x, 5, 6, 7, 4);
    salsa20_quarter_round(x, 10, 11, 8, 9);
    salsa20_quarter_round(x, 15, 12, 13, 14);
  }

  for (int i = 0; i < 16; i++) out[i] = x[i] + in[i];
}

// Salsa20 decryption
bool salsa20_decrypt(uint8_t *data, size_t len) {
  if (len < 0x13C) return false;  // GT7 packet is 316 bytes (0x13C)

  // Extract IV from packet
  uint32_t iv1 = data[0x40] | (data[0x41] << 8) | (data[0x42] << 16) | (data[0x43] << 24);
  uint32_t iv2 = iv1 ^ 0xDEADBEEF;

  // Setup Salsa20 state
  uint32_t state[16];
  
  // Constants
  const uint32_t constants[4] = {0x61707865, 0x3320646e, 0x79622d32, 0x6b206574};
  state[0] = constants[0];
  state[5] = constants[1];
  state[10] = constants[2];
  state[15] = constants[3];

  // Key (256 bits = 32 bytes)
  // First 16 bytes go into state[1-4]
  for (int i = 0; i < 4; i++) {
    state[1 + i] = ((uint32_t)SALSA20_KEY[i * 4]) |
                   ((uint32_t)SALSA20_KEY[i * 4 + 1] << 8) |
                   ((uint32_t)SALSA20_KEY[i * 4 + 2] << 16) |
                   ((uint32_t)SALSA20_KEY[i * 4 + 3] << 24);
  }
  // Last 16 bytes go into state[11-14]
  for (int i = 0; i < 4; i++) {
    state[11 + i] = ((uint32_t)SALSA20_KEY[16 + i * 4]) |
                    ((uint32_t)SALSA20_KEY[16 + i * 4 + 1] << 8) |
                    ((uint32_t)SALSA20_KEY[16 + i * 4 + 2] << 16) |
                    ((uint32_t)SALSA20_KEY[16 + i * 4 + 3] << 24);
  }

  // Nonce (IV)
  state[6] = iv2;
  state[7] = iv1;

  // Block counter
  state[8] = 0;
  state[9] = 0;

  // Decrypt in blocks of 64 bytes
  uint32_t keystream[16];
  for (size_t i = 0; i < len; i += 64) {
    salsa20_block(keystream, state);
    
    size_t blockLen = (len - i < 64) ? (len - i) : 64;
    for (size_t j = 0; j < blockLen; j++) {
      data[i + j] ^= ((uint8_t*)keystream)[j];
    }
    
    // Increment block counter
    state[8]++;
    if (state[8] == 0) state[9]++;
  }

  // Check magic number
  uint32_t magic = data[0] | (data[1] << 8) | (data[2] << 16) | (data[3] << 24);
  return (magic == 0x47375330);
}

// Send heartbeat to PS4
void sendHeartbeat() {
  udp.beginPacket(ps4IP, SendPort);
  udp.write((uint8_t)'B');
  udp.endPacket();
}

// Blink LED (LED is active-low: LOW=on, HIGH=off)
void blinkLED(int times, int delayMs) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_BUILTIN, LOW);   // Turn on
    delay(delayMs);
    digitalWrite(LED_BUILTIN, HIGH);  // Turn off
    delay(delayMs);
  }
}

void setup() {
  // Initialize serial
  Serial.begin(115200);
  delay(1000);
  Serial.println("\nGT7 Telemetry Motion Data Reader");
  Serial.println("ESP32-C3 Super Mini");
  
  // Initialize LED (active-low: LOW=on, HIGH=off)
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);  // Turn off
  
  // Connect to WiFi
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  
  // Blink LED while connecting to WiFi
  bool ledState = false;
  while (WiFi.status() != WL_CONNECTED) {
    ledState = !ledState;
    digitalWrite(LED_BUILTIN, ledState ? HIGH : LOW);
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\nWiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
  Serial.print("WiFi signal strength: ");
  Serial.print(WiFi.RSSI());
  Serial.println(" dBm");
  
  // Blink LED twice fast after WiFi connection, then turn off
  blinkLED(2, 100);
  
  // Turn off LED until GT7 packets are received
  digitalWrite(LED_BUILTIN, HIGH);
  
  // Print PS4 IP address
  Serial.print("\nPS4 IP Address: ");
  Serial.println(ps4IP);
  
  // Ping PS4 to check if it's reachable
  Serial.println("Pinging PS4 (3 attempts)...");
  bool pingSuccess = Ping.ping(ps4IP, 3);
  
  if (pingSuccess) {
    Serial.println("Ping SUCCESS!");
    Serial.print("  Average latency: ");
    Serial.print(Ping.averageTime());
    Serial.println(" ms");
    Serial.print("  Min latency: ");
    Serial.print(Ping.minTime());
    Serial.println(" ms");
    Serial.print("  Max latency: ");
    Serial.print(Ping.maxTime());
    Serial.println(" ms");
  } else {
    Serial.println("Ping FAILED!");
    Serial.println("Warning: PS4 is not responding to ping.");
    Serial.println("Make sure PS4 is on and GT7 is running.");
  }
  
  // Start UDP
  udp.begin(ReceivePort);
  Serial.print("\nListening on UDP port: ");
  Serial.println(ReceivePort);
  
  // Send initial heartbeat
  sendHeartbeat();
  Serial.println("Heartbeat sent to PS4");
  Serial.println("\nWaiting for GT7 telemetry packets...");
  Serial.println("Sway (m/s²), Heave (m/s²), Surge (m/s²)");
}

unsigned long lastHeartbeat = 0;
unsigned long lastPacketTime = 0;
unsigned long lastDebugPrint = 0;
unsigned long packetCount = 0;
unsigned long heartbeatCount = 0;

void loop() {
  // Send heartbeat every 10 seconds
  if (millis() - lastHeartbeat > 10000) {
    sendHeartbeat();
    lastHeartbeat = millis();
    heartbeatCount++;
  }
  
  // Check for incoming packets
  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    packetCount++;
    
    // Read packet
    int len = udp.read(packetBuffer, sizeof(packetBuffer));
    
    if (len >= 0x13C) {  // Minimum packet size with acceleration data (316 bytes)
      // Decrypt packet
      if (salsa20_decrypt(packetBuffer, len)) {
        // Turn on LED when packet is successfully decrypted (active-low)
        digitalWrite(LED_BUILTIN, LOW);
        
        lastPacketTime = millis();
        
        // Extract position (signed short at 0x84)
        int16_t currentPosition;
        memcpy(&currentPosition, &packetBuffer[0x84], 2);
        
        // Extract acceleration values (floats at specific offsets)
        // Sway (X axis - lateral) at 0x130 (304)
        // Heave (Y axis - vertical) at 0x134 (308)  
        // Surge (Z axis - longitudinal) at 0x138 (312)
        
        float accelSway, accelHeave, accelSurge;
        memcpy(&accelSway, &packetBuffer[0x130], 4);
        memcpy(&accelHeave, &packetBuffer[0x134], 4);
        memcpy(&accelSurge, &packetBuffer[0x138], 4);
        
        // Print acceleration values to serial with position and WiFi signal strength
        Serial.print("P:");
        Serial.print(currentPosition);
        Serial.print(",");
        Serial.print("Sw:");
        Serial.print(accelSway, 2);
        Serial.print(",");
        Serial.print("Hv:");
        Serial.print(accelHeave, 2);
        Serial.print(",");
        Serial.print("Sg:");
        Serial.print(accelSurge, 2);
        Serial.print(",");
        Serial.print("SS:");
        Serial.print(WiFi.RSSI()/10.0, 1);
        Serial.println("");
        
        // Turn off LED after finishing parsing the packet data (active-low)
        digitalWrite(LED_BUILTIN, HIGH);
      }
    }
  }
  
  delay(1);  // Small delay to prevent watchdog issues
}
