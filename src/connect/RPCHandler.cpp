#include "RPCHandler.h"
#include "../Device/LEDTask.h"
#include <Arduino.h>
#include <Server_Side_RPC.h>

void onSetValue(const JsonVariantConst &params, JsonDocument &response) {
    if (!params.containsKey(LED_KEY)) {
        Serial.println("[RPC] setValue: missing key 'led'");
        response["error"] = "missing key 'led'";
        return;
    }
    bool newState = params[LED_KEY].as<bool>();
    ledState = newState;
    xQueueOverwrite(ledQueue, &newState);
    Serial.printf("[RPC] setValue led = %s\n", newState ? "true" : "false");
    response[LED_KEY] = newState;
}