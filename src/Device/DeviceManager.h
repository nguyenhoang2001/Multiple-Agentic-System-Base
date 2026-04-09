#pragma once
#include "IDevice.h"
#include <vector>
#include <memory>

class DeviceManager {
private:
    static DeviceManager* instance;
    std::vector<std::shared_ptr<IDevice>> devices;

    DeviceManager() = default;

public:
    static DeviceManager* getInstance();
    
    // Prevent copy
    DeviceManager(const DeviceManager&) = delete;
    DeviceManager& operator=(const DeviceManager&) = delete;

    // Device management
    void registerDevice(std::shared_ptr<IDevice> device);
    IDevice* getDevice(const char* deviceId);
    IDevice* getDeviceByName(const char* name);
    
    // Get all devices
    const std::vector<std::shared_ptr<IDevice>>& getDevices() const;

    // RPC handling
    bool handleRPC(const char* deviceId, const char* method, 
                   const JsonVariantConst &params, JsonDocument &response);

    // Attribute synchronization with ThingsBoard
    JsonObject getAllPendingAttributes();
    void clearAllPendingFlags();

    // Process all devices
    void processAll();

    // Debug/Info
    void printDevicesInfo();
};
