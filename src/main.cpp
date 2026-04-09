#include <Arduino.h>
#include "config.h"
#include "connect/WiFiManager.h"
#include "Device/LEDTask.h"
#include "Device/DeviceManager.h"
#include "Device/SmartLight.h"
#include "Device/SmartFan.h"
#include "connect/TBClient.h"

void setup() {
    Serial.begin(SERIAL_BAUD);
    vTaskDelay(pdMS_TO_TICKS(1000));
    Serial.println("\n[Boot] CoreIoT Multi-Device Manager");

    // Initialize DeviceManager and register devices
    DeviceManager* dm = DeviceManager::getInstance();
    
    // Register devices
    dm->registerDevice(std::make_shared<SmartLight>("Đèn trần", TOKEN, DEVICE_ID, LED_PIN));
    dm->registerDevice(std::make_shared<SmartFan>("quạt trần", TOKEN, DEVICE_ID, 47));
    
    InitWiFi();

    // deviceTask on Core 0
    xTaskCreatePinnedToCore(deviceTask, "device_task", 2048, nullptr, 1, nullptr, 0);

    // tbTask on Core 1 for MQTT handling
    xTaskCreatePinnedToCore(tbTask, "tb_task", 4096, nullptr, 1, nullptr, 1);
}

void loop() {
    vTaskDelete(NULL);
}