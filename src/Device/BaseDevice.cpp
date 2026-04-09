#include "BaseDevice.h"
#include <Arduino.h>
#include <cstring>

BaseDevice::BaseDevice(const char* name, const char* token, const char* id, const char* type)
    : name(name), deviceToken(token), deviceId(id), deviceType(type) {
}

const char* BaseDevice::getName() const {
    return name.c_str();
}

const char* BaseDevice::getDeviceToken() const {
    return deviceToken.c_str();
}

const char* BaseDevice::getDeviceId() const {
    return deviceId.c_str();
}

const char* BaseDevice::getType() const {
    return deviceType.c_str();
}

JsonObject BaseDevice::getAttributes() {
    return attributesDoc.as<JsonObject>();
}

void BaseDevice::registerRPCHandler(const char* methodName, RPC_Handler handler) {
    rpcHandlers[methodName] = handler;
}

bool BaseDevice::handleRPC(const char* methodName, const JsonVariantConst &params, JsonDocument &response) {
    auto it = rpcHandlers.find(methodName);
    if (it != rpcHandlers.end()) {
        it->second(params, response);
        return true;
    }
    return false;
}

bool BaseDevice::setAttribute(const char* key, const JsonVariant &value) {
    if (!attributesDoc[key].isNull()) {  // Check if key exists
        attributesDoc[key] = value;
        pendingDoc[key] = value;
        return true;
    }
    return false;
}

bool BaseDevice::setAttribute(const char* key, bool value) {
    if (!attributesDoc[key].isNull()) {  // Check if key exists
        attributesDoc[key] = value;
        pendingDoc[key] = value;
        return true;
    }
    return false;
}

bool BaseDevice::setAttribute(const char* key, int value) {
    if (!attributesDoc[key].isNull()) {  // Check if key exists
        attributesDoc[key] = value;
        pendingDoc[key] = value;
        return true;
    }
    return false;
}

bool BaseDevice::setAttribute(const char* key, const char* value) {
    if (!attributesDoc[key].isNull()) {  // Check if key exists
        attributesDoc[key] = value;
        pendingDoc[key] = value;
        return true;
    }
    return false;
}

JsonVariant BaseDevice::getAttribute(const char* key) {
    return attributesDoc[key];
}

void BaseDevice::markAttributePending(const char* key) {
    if (key == nullptr) {
        // Mark all attributes as pending
        for (auto kvp : attributesDoc.as<JsonObject>()) {
            pendingDoc[kvp.key()] = kvp.value();
        }
    } else {
        if (!attributesDoc[key].isNull()) {  // Check if key exists
            pendingDoc[key] = attributesDoc[key];
        }
    }
}

JsonObject BaseDevice::getPendingAttributes() {
    return pendingDoc.as<JsonObject>();
}

void BaseDevice::clearPendingFlags() {
    pendingDoc.clear();
}

void BaseDevice::initializeAttribute(const char* key, const char* type) {
    // Initialize with default values based on type
    if (strcmp(type, "boolean") == 0) {
        attributesDoc[key] = false;
    } else if (strcmp(type, "integer") == 0) {
        attributesDoc[key] = 0;
    } else if (strcmp(type, "string") == 0) {
        attributesDoc[key] = "";
    }
}
