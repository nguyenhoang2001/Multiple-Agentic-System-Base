#include "LEDTask.h"
#include "../config.h"
#include <Arduino.h>

volatile bool ledState = false;
volatile bool pendingAttrUpdate = false;
QueueHandle_t ledQueue = nullptr;

void ledTask(void *pvParameters) {
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);

    bool state = false;
    for (;;) {
        if (xQueueReceive(ledQueue, &state, portMAX_DELAY) == pdTRUE) {
            digitalWrite(LED_PIN, state ? HIGH : LOW);
            Serial.printf("[LED] %s\n", state ? "ON" : "OFF");
            pendingAttrUpdate = true;
        }
    }
}