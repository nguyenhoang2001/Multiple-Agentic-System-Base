#include "WiFiManager.h"
#include "../src/config.h"
#include <Arduino.h>

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
    if (WiFi.status() == WL_CONNECTED) return true;
    Serial.println("[WiFi] Lost, reconnecting...");
    InitWiFi();
    return true;
}