#include <Arduino.h>
#include "config.h"
#include "connect/WiFiManager.h"
#include "Device/LEDTask.h"
#include "connect/TBClient.h"
#include "connect/RPCHandler.h"

void setup() {
    Serial.begin(SERIAL_BAUD);
    vTaskDelay(pdMS_TO_TICKS(1000));
    Serial.println("\n[Boot] CoreIoT LED – Server-Side RPC 2-way");

    ledQueue = xQueueCreate(1, sizeof(bool));
    configASSERT(ledQueue);

    // ledTask on Core 0
    xTaskCreatePinnedToCore(ledTask, "led_task", 2048, nullptr, 1, nullptr, 0);

    InitWiFi();

    // Kích hoạt cờ gửi trạng thái mặc định (false) lên ThingsBoard
    pendingAttrUpdate = true;

    // tbTask on Core 1 for MQTT handling
    xTaskCreatePinnedToCore(tbTask, "tb_task", 4096, nullptr, 1, nullptr, 1);
}

void loop() {
    vTaskDelete(NULL);
}