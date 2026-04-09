#include "DeviceManager.h"
#include <Arduino.h>

DeviceManager* DeviceManager::instance = nullptr;

DeviceManager* DeviceManager::getInstance() {
    if (instance == nullptr) {
        instance = new DeviceManager();
    }
    return instance;
}

void DeviceManager::registerDevice(std::shared_ptr<IDevice> device) {
    if (device) {
        devices.push_back(device);
        Serial.printf("[DeviceManager] Device registered: %s (ID: %s)\n", 
                     device->getName(), device->getDeviceId());
    }
}

IDevice* DeviceManager::getDevice(const char* deviceId) {
    for (auto& device : devices) {
        if (strcmp(device->getDeviceId(), deviceId) == 0) {
            return device.get();
        }
    }
    return nullptr;
}

IDevice* DeviceManager::getDeviceByName(const char* name) {
    for (auto& device : devices) {
        if (strcmp(device->getName(), name) == 0) {
            return device.get();
        }
    }
    return nullptr;
}

const std::vector<std::shared_ptr<IDevice>>& DeviceManager::getDevices() const {
    return devices;
}

bool DeviceManager::handleRPC(const char* deviceId, const char* method,
                              const JsonVariantConst &params, JsonDocument &response) {
    IDevice* device = getDevice(deviceId);
    if (device) {
        return device->handleRPC(method, params, response);
    }
    return false;
}

JsonObject DeviceManager::getAllPendingAttributes() {
    JsonDocument doc;
    for (auto& device : devices) {
        JsonObject pending = device->getPendingAttributes();
        for (auto kvp : pending) {
            doc[kvp.key()] = kvp.value();
        }
    }
    return doc.as<JsonObject>();
}

void DeviceManager::clearAllPendingFlags() {
    for (auto& device : devices) {
        device->clearPendingFlags();
    }
}

void DeviceManager::processAll() {
    for (auto& device : devices) {
        device->process();
    }
}

void DeviceManager::printDevicesInfo() {
    Serial.println("\n[DeviceManager] Registered Devices:");
    Serial.printf("Total: %d devices\n", devices.size());
    for (auto& device : devices) {
        Serial.printf("  - Name: %s\n    Type: %s\n    ID: %s\n    Token: %s\n",
                     device->getName(), device->getType(), 
                     device->getDeviceId(), device->getDeviceToken());
    }
    Serial.println("");
}
