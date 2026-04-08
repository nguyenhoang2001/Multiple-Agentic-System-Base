#include "TBClient.h"
#include "../config.h"
#include "../connect/RPCHandler.h"
#include "../device/LEDTask.h"
#include "../src/connect/WiFiManager.h"
#include <Arduino.h>
#include <array>

WiFiClient espClient;
Arduino_MQTT_Client mqttClient(espClient);
Server_Side_RPC<MAX_RPC_SUBS, MAX_RPC_RESP> rpc;

const std::array<IAPI_Implementation *, 1U> apis = {&rpc};
ThingsBoard tb(mqttClient, MAX_MSG_SIZE, MAX_MSG_SIZE, Default_Max_Stack_Size, apis);

static bool subscribed = false;
const std::array<RPC_Callback, MAX_RPC_SUBS> callbacks = {
    RPC_Callback(RPC_SET_VALUE, onSetValue)
};

void tbTask(void *pvParameters) {
    for (;;) {
        if (!tb.connected()) {
            Serial.printf("[TB] Connecting to %s ...\n", THINGSBOARD_SERVER);
            if (!tb.connect(THINGSBOARD_SERVER, TOKEN, THINGSBOARD_PORT, DEVICE_ID)) {
                Serial.println("[TB] Connection failed, retry in 5 s");
                vTaskDelay(pdMS_TO_TICKS(5000));
                continue;
            }
            Serial.println("[TB] Connected");
        }

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

        if (pendingAttrUpdate) {
            pendingAttrUpdate = false;
            tb.sendAttributeData(LED_KEY, (bool)ledState);
            Serial.printf("[Attr] led = %s\n", ledState ? "true" : "false");
        }

        tb.loop();
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}