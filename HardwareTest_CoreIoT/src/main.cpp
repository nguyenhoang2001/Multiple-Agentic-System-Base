#include <Arduino.h>
#include <WiFi.h>
#include <Arduino_MQTT_Client.h>
#include <Server_Side_RPC.h>
#include <ThingsBoard.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

// ── Configuration ─────────────────────────────────────────────────────────────
constexpr char     WIFI_SSID[]          = "ACLAB";
constexpr char     WIFI_PASSWORD[]      = "ACLAB2023";
constexpr char     TOKEN[]              = "xdF2nW4aR9SAdqqPiym0";
constexpr char     DEVICE_ID[]          = "fcceeaa0-3111-11f1-9981-cffbb69f5b14";
constexpr char     THINGSBOARD_SERVER[] = "app.coreiot.io";
constexpr uint16_t THINGSBOARD_PORT     = 1883U;
constexpr uint32_t SERIAL_BAUD          = 115200U;

// ── Keys / RPC ────────────────────────────────────────────────────────────────
constexpr char    LED_CELLING_KEY[] = "led_celling";
constexpr char    LED_NIGHT_KEY[]   = "led_beside_night_light";
constexpr char    COLOR_NIGHT_KEY[] = "brightness_beside_night_light";
constexpr char    FAN_SPEED_KEY[]   = "integer_fan_speed";

constexpr char    RPC_SET_VALUE[]   = "setValue";
constexpr uint8_t MAX_RPC_SUBS      = 1U;
constexpr uint8_t MAX_RPC_RESP      = 5U; // Tăng lên 5 để tránh lỗi "response overflowed" gây ra HTTP 408 Timeout

// ── Hardware ──────────────────────────────────────────────────────────────────
#include <Adafruit_NeoPixel.h>
constexpr int LED_CELLING_PIN = 48; // Pin for Celling LED
constexpr int FAN_PIN         = 3;  // Example Pin for Fan PWM
constexpr int RGB_PIN         = 6;  // Cập nhật PIN RGB thành 6 theo sơ đồ LED
constexpr int NUM_PIXELS      = 4;  // Module 4 RGB LEDs

Adafruit_NeoPixel pixels(NUM_PIXELS, RGB_PIN, NEO_GRB + NEO_KHZ800);

// ── ThingsBoard objects ───────────────────────────────────────────────────────
constexpr uint16_t MAX_MSG_SIZE = 1024U; // Increased to 1024 to handle larger JSON payloads

WiFiClient          espClient;
Arduino_MQTT_Client mqttClient(espClient);
Server_Side_RPC<MAX_RPC_SUBS, MAX_RPC_RESP> rpc;
const std::array<IAPI_Implementation *, 1U> apis = {&rpc};
// Set keepAlive time to 60s instead of default (15s) to avoid unneeded disconnects
ThingsBoard tb(mqttClient, MAX_MSG_SIZE, MAX_MSG_SIZE, Default_Max_Stack_Size, apis);

// ── Shared state ──────────────────────────────────────────────────────────────
static volatile bool ledCellingState   = false;
static volatile bool nightLightState   = false;  // Biến ảo tắt/mở chung
static volatile int  nightLightColor   = 0;      // 0-Red, 1-Green, 2-Blue
static volatile int  fanSpeed          = 0;      // 0-off, 1-low, 2-medium, 3-high

static volatile bool pendingAttrUpdate = false;
static bool          subscribed        = false;

// ── Queue: loop() → ledTask ───────────────────────────────────────────────────
static QueueHandle_t ledQueue = nullptr;

// ─────────────────────────────────────────────────────────────────────────────
// RPC callback: setValue { "key": value, ... }
// ─────────────────────────────────────────────────────────────────────────────
void onSetValue(const JsonVariantConst &params, JsonDocument &response) {
    bool hasUpdates = false;

    // 1. led_celling
    if (params.containsKey(LED_CELLING_KEY)) {
        ledCellingState = params[LED_CELLING_KEY].as<bool>();
        response[LED_CELLING_KEY] = ledCellingState;
        hasUpdates = true;
    }
    
    // 2. led_beside_night_light
    if (params.containsKey(LED_NIGHT_KEY)) {
        nightLightState = params[LED_NIGHT_KEY].as<bool>();
        response[LED_NIGHT_KEY] = nightLightState;
        hasUpdates = true;
    }
    
    // 3. brightness_beside_night_light (RGB color)
    if (params.containsKey(COLOR_NIGHT_KEY)) {
        nightLightColor = params[COLOR_NIGHT_KEY].as<int>();
        response[COLOR_NIGHT_KEY] = nightLightColor;
        hasUpdates = true;
    }

    // 4. integer_fan_speed
    if (params.containsKey(FAN_SPEED_KEY)) {
        fanSpeed = params[FAN_SPEED_KEY].as<int>();
        response[FAN_SPEED_KEY] = fanSpeed;
        hasUpdates = true;
    }

    if (!hasUpdates) {
        Serial.println("[RPC] setValue: missing target keys");
        response["error"] = "missing target keys";
        return;
    }

    bool dummy = true;
    xQueueOverwrite(ledQueue, &dummy); // Signal hardware task to update states
    
    Serial.printf("[RPC] Received updates -> Cell:%d, Night:%d, Color:%d, Fan:%d\n", 
            ledCellingState, nightLightState, nightLightColor, fanSpeed);
}

// Global scope for callbacks to ensure memory is retained
// IMPORTANT: Đổi MAX_RPC_RESP thành số lớn hơn để buffer ko bị tràn nếu gửi/nhận liền mạch
// Tuy nhiên mảng config ban đầu định nghĩa MAX_RPC_RESP = 1U nên mình sẽ không đổi macro
const std::array<RPC_Callback, MAX_RPC_SUBS> callbacks = {
    RPC_Callback(RPC_SET_VALUE, onSetValue)
};

// ─────────────────────────────────────────────────────────────────────────────
// WiFi helpers – mirrors example InitWiFi / reconnect
// ─────────────────────────────────────────────────────────────────────────────
void InitWiFi() {
    Serial.print("[WiFi] Connecting");
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.printf("\n[WiFi] Connected  IP: %s\n", WiFi.localIP().toString().c_str());
}

bool reconnect() {
    if (WiFi.status() == WL_CONNECTED) {
        return true;
    }
    Serial.println("[WiFi] Lost, reconnecting...");
    InitWiFi();
    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// FreeRTOS Task: Hardware control – only touches GPIO/Libraries (Core 0)
// ─────────────────────────────────────────────────────────────────────────────
void ledTask(void *pvParameters) {
    // 1. NeoPixel Init
    pixels.begin();
    pixels.clear();
    pixels.show();

    // 2. LED Celling Init
    pinMode(LED_CELLING_PIN, OUTPUT);
    digitalWrite(LED_CELLING_PIN, LOW);

    // 3. Fan Init (PWM)
    // On ESP32, analogWrite is a wrapper for ledc/mcpwm or uses the standard ESP32 
    // analogWrite implementation which works transparently.
    pinMode(FAN_PIN, OUTPUT);
    analogWrite(FAN_PIN, 0);

    bool signal;
    
    for (;;) {
        // Block until a new RPC command arrives
        if (xQueueReceive(ledQueue, &signal, portMAX_DELAY) == pdTRUE) {
            
            // 1. Cập nhật Đèn trần (Celling LED)
            digitalWrite(LED_CELLING_PIN, ledCellingState ? HIGH : LOW);
            
            // 2. Cập nhật Đèn ngủ (NeoPixel)
            pixels.clear();
            if (nightLightState) {
                // Determine color based on index: 0-Red, 1-Green, 2-Blue
                uint32_t color = pixels.Color(255, 255, 255); // Default to white
                if (nightLightColor == 0)      color = pixels.Color(255, 0, 0); // Red
                else if (nightLightColor == 1) color = pixels.Color(0, 255, 0); // Green
                else if (nightLightColor == 2) color = pixels.Color(0, 0, 255); // Blue
                
                for(int p = 0; p < NUM_PIXELS; p++) {
                    pixels.setPixelColor(p, color);
                }
            }
            pixels.show(); // Apply new color immediately
            
            // 3. Cập nhật Bơm/Quạt (Fan) theo Speed (0-3)
            int pwmVal = 0;
            switch (fanSpeed) {
                case 1: pwmVal = 85;  break; // Low
                case 2: pwmVal = 170; break; // Medium
                case 3: pwmVal = 255; break; // High
                default: pwmVal = 0;  break; // Off
            }
            analogWrite(FAN_PIN, pwmVal);

            Serial.printf("[HW] Applied -> Cell:%s, NeoPixel:%s, ColorIdx:%d, PWM:%d\n", 
                          ledCellingState ? "ON" : "OFF", nightLightState ? "ON" : "OFF" , nightLightColor, pwmVal);
            
            // Báo cho tbTask biết -> gửi update lên ThingsBoard
            pendingAttrUpdate = true;
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// FreeRTOS Task: ThingsBoard MQTT & RPC (Core 1)
// ─────────────────────────────────────────────────────────────────────────────
void tbTask(void *pvParameters) {
    for (;;) {
        if (!reconnect()) {
            vTaskDelay(pdMS_TO_TICKS(10));
            continue;
        }

        if (!tb.connected()) {
            Serial.printf("[TB] Connecting to %s ...\n", THINGSBOARD_SERVER);
            
            // Sử dụng TOKEN làm ClientID để đảm bảo tính độc nhất trên Server
            // Việc thiết lập ClientID giúp tránh tình trạng bị máy chủ ngắt kết nối do trùng lặp thiết bị (Collision)
            if (!tb.connect(THINGSBOARD_SERVER, TOKEN, THINGSBOARD_PORT, DEVICE_ID)) {
                Serial.println("[TB] Connection failed, retry in 5 s");
                vTaskDelay(pdMS_TO_TICKS(5000));
                continue;
            }
            Serial.println("[TB] Connected");
        }

        // Subscribe once – never reset subscribed after true (library handles MQTT resubscription)
        if (!subscribed) {
            Serial.println("[TB] Subscribing for RPC...");
            if (!rpc.RPC_Subscribe(callbacks.cbegin(), callbacks.cend())) {
                Serial.println("[TB] Subscribe failed");
                vTaskDelay(pdMS_TO_TICKS(1000));
                continue;
            }
            Serial.println("[TB] Subscribed to RPC: setValue");
            subscribed = true;
        }

        // Send pending client attribute (triggered by RPC callback)
        if (pendingAttrUpdate) {
            pendingAttrUpdate = false;
            
            // Build an array of all properties to dispatch them in batch
            constexpr size_t ATTR_COUNT = 4U;
            Attribute attributes[ATTR_COUNT] = {
                { LED_CELLING_KEY, (bool)ledCellingState },
                { LED_NIGHT_KEY,   (bool)nightLightState },
                { COLOR_NIGHT_KEY, (int)nightLightColor  },
                { FAN_SPEED_KEY,   (int)fanSpeed         }
            };
            
            // Send mapping array directly to ThingsBoard using pointers
            Telemetry* attrBegin = attributes;
            Telemetry* attrEnd = attributes + ATTR_COUNT;
            
            // Add template parameter <ATTR_COUNT> to specify the memory size statically
            tb.sendAttributes<ATTR_COUNT>(attrBegin, attrEnd);
            
            Serial.println("[TB] Shared attributes synchronized to server.");
        }

        tb.loop();
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Arduino entry points
// ─────────────────────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(SERIAL_BAUD);
    vTaskDelay(pdMS_TO_TICKS(1000));
    Serial.println("\n[Boot] CoreIoT LED – Server-Side RPC 2-way");

    ledQueue = xQueueCreate(1, sizeof(bool));
    configASSERT(ledQueue);

    // ledTask on Core 0
    xTaskCreatePinnedToCore(ledTask, "led_task", 2048, nullptr, 1, nullptr, 0);

    InitWiFi();

    // Khởi động bằng việc bắn ngay 1 tín hiệu vào Queue để phần cứng tự động
    // Set chân mức 0, cập nhật LED RGB về tắt, Fan về 0
    // Và sau đó Hardware task sẽ tự động bật cờ `pendingAttrUpdate = true;` 
    // để TbTask kéo TẤT CẢ 4 biến lên Server lúc boot
    bool bootDummy = true;
    xQueueOverwrite(ledQueue, &bootDummy);

    // tbTask on Core 1 for MQTT handling
    xTaskCreatePinnedToCore(tbTask, "tb_task", 4096, nullptr, 1, nullptr, 1);
}

void loop() {
    // Trong RTOS, xóa task loop mặc định để tiết kiệm tài nguyên (giữ function trống)
    vTaskDelete(NULL);
}
