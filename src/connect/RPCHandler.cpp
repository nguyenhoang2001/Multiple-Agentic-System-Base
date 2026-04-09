#include "RPCHandler.h"
#include "../Device/DeviceManager.h"
#include <Arduino.h>
#include <string>

void handleRPCCall(const char* method, const char* params, std::string& response) {
    JsonDocument reqDoc;
    JsonDocument respDoc;
    
    // Parse incoming parameters
    DeserializationError error = deserializeJson(reqDoc, params);
    if (error) {
        respDoc["error"] = "Invalid JSON";
        serializeJson(respDoc, response);
        return;
    }
    
    // Extract device ID from the method (format: "deviceId_methodName")
    // Or use a global device ID from config
    
    DeviceManager* dm = DeviceManager::getInstance();
    
    // Try to find device by name or use default
    const char* deviceId = DEVICE_ID;  // From config.h
    
    Serial.printf("[RPC] Handling method: %s with params: %s\n", method, params);
    
    if (dm->handleRPC(deviceId, method, reqDoc.as<JsonVariantConst>(), respDoc)) {
        serializeJson(respDoc, response);
    } else {
        respDoc["error"] = "Method or device not found";
        serializeJson(respDoc, response);
    }
}