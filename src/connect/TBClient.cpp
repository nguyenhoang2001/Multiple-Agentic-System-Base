#include "TBClient.h"
#include "RPCHandler.h"
#include "../Device/DeviceManager.h"
#include "../src/connect/WiFiManager.h"
#include <Arduino.h>
#include <array>
#include <string>

WiFiClient espClient;
Arduino_MQTT_Client mqttClient(espClient);
Server_Side_RPC<MAX_RPC_SUBS, MAX_RPC_RESP> rpc;

const std::array<IAPI_Implementation *, 1U> apis = {&rpc};
ThingsBoard tb(mqttClient, MAX_MSG_SIZE, MAX_MSG_SIZE, Default_Max_Stack_Size, apis);

static bool subscribed = false;
static unsigned long lastAttrUpdate = 0;

// Generic RPC handler that delegates to DeviceManager
void rpcCallbackHandler(const JsonVariantConst &params, JsonDocument &response) {
    const char* methodName = "setValue";  // Will be extracted from RPC context
    std::string jsonStr;
    handleRPCCall(methodName, "", jsonStr);
}

void tbTask(void *pvParameters) {
    DeviceManager* dm = DeviceManager::getInstance();
    
    for (;;) {
        if (!tb.connected()) {
            Serial.printf("[TB] Connecting to %s ...\n", THINGSBOARD_SERVER);
            if (!tb.connect(THINGSBOARD_SERVER, TOKEN, THINGSBOARD_PORT, DEVICE_ID)) {
                Serial.println("[TB] Connection failed, retry in 5 s");
                vTaskDelay(pdMS_TO_TICKS(5000));
                continue;
            }
            Serial.println("[TB] Connected");
            subscribed = false;  // Reset subscription flag
        }

        if (!subscribed) {
            Serial.println("[TB] Subscribing for RPC...");
            
            // Subscribe to all methods from config
            const std::array<RPC_Callback, MAX_RPC_SUBS> callbacks = {
                RPC_Callback("setValue", rpcCallbackHandler),
                // RPC_Callback("setSpeed", rpcCallbackHandler),
                // Add more callbacks as needed
            };
            
            if (!rpc.RPC_Subscribe(callbacks.cbegin(), callbacks.cend())) {
                Serial.println("[TB] Subscribe failed");
                vTaskDelay(pdMS_TO_TICKS(1000));
                continue;
            }
            Serial.println("[TB] Subscribed to RPC callbacks");
            subscribed = true;
        }

        // Send pending attribute updates every 5 seconds
        unsigned long now = millis();
        if (now - lastAttrUpdate > 5000) {
            lastAttrUpdate = now;
            
            // Send attributes from all devices
            for (const auto& device : dm->getDevices()) {
                JsonObject attrs = device->getAttributes();
                for (auto kvp : attrs) {
                    // Convert JsonString to const char*
                    const char* key = kvp.key().c_str();
                    
                    // Send based on value type
                    if (kvp.value().is<bool>()) {
                        tb.sendAttributeData(key, kvp.value().as<bool>());
                    } else if (kvp.value().is<int>()) {
                        tb.sendAttributeData(key, kvp.value().as<int>());
                    } else if (kvp.value().is<const char*>()) {
                        tb.sendAttributeData(key, kvp.value().as<const char*>());
                    }
                    
                    Serial.printf("[TB] Sent attribute: %s = ", key);
                    serializeJson(kvp.value(), Serial);
                    Serial.println();
                }
            }
        }

        tb.loop();
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}