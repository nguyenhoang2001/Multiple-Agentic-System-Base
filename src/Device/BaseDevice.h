#pragma once
#include "IDevice.h"
#include <map>
#include <string>

class BaseDevice : public IDevice {
protected:
    std::string name;
    std::string deviceToken;
    std::string deviceId;
    std::string deviceType;
    
    // Attributes storage
    JsonDocument attributesDoc;
    JsonDocument pendingDoc;
    
    // RPC Handlers map
    std::map<std::string, RPC_Handler> rpcHandlers;

public:
    BaseDevice(const char* name, const char* token, const char* id, const char* type);
    virtual ~BaseDevice() = default;

    // IDevice implementation
    const char* getName() const override;
    const char* getDeviceToken() const override;
    const char* getDeviceId() const override;
    const char* getType() const override;

    JsonObject getAttributes() override;
    void registerRPCHandler(const char* methodName, RPC_Handler handler) override;
    bool handleRPC(const char* methodName, const JsonVariantConst &params, JsonDocument &response) override;
    bool setAttribute(const char* key, const JsonVariant &value) override;
    bool setAttribute(const char* key, bool value);
    bool setAttribute(const char* key, int value);
    bool setAttribute(const char* key, const char* value);
    JsonVariant getAttribute(const char* key) override;
    void markAttributePending(const char* key = nullptr) override;
    JsonObject getPendingAttributes() override;
    void clearPendingFlags() override;

    // Virtual methods for subclasses
    virtual void process() override = 0;

protected:
    // Helper to initialize attributes
    void initializeAttribute(const char* key, const char* type);
};
