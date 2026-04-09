#pragma once
#include <ArduinoJson.h>
#include <functional>
#include <string>

// Callback type for RPC handlers
using RPC_Handler = std::function<void(const JsonVariantConst &params, JsonDocument &response)>;

class IDevice {
public:
    virtual ~IDevice() = default;

    // Getters
    virtual const char* getName() const = 0;
    virtual const char* getDeviceToken() const = 0;
    virtual const char* getDeviceId() const = 0;
    virtual const char* getType() const = 0;

    // Get all shared attributes (key-value pairs)
    virtual JsonObject getAttributes() = 0;

    // Register RPC handler for this device
    virtual void registerRPCHandler(const char* methodName, RPC_Handler handler) = 0;

    // Handle incoming RPC call
    virtual bool handleRPC(const char* methodName, const JsonVariantConst &params, JsonDocument &response) = 0;

    // Update attribute value
    virtual bool setAttribute(const char* key, const JsonVariant &value) = 0;

    // Get attribute value
    virtual JsonVariant getAttribute(const char* key) = 0;

    // Process device logic (called by FreeRTOS task)
    virtual void process() = 0;

    // Mark attribute as pending for update to ThingsBoard
    virtual void markAttributePending(const char* key = nullptr) = 0;

    // Get pending attributes for sync with ThingsBoard
    virtual JsonObject getPendingAttributes() = 0;

    // Clear pending flags after sync
    virtual void clearPendingFlags() = 0;
};
