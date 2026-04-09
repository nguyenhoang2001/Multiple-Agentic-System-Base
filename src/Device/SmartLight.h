#pragma once
#include "BaseDevice.h"

class SmartLight : public BaseDevice {
private:
    int ledPin;
    bool ledState;

public:
    SmartLight(const char* name, const char* token, const char* id, int pin);
    ~SmartLight();

    void process() override;

    // RPC handlers
    void onSetValue(const JsonVariantConst &params, JsonDocument &response);
    void onSetBrightness(const JsonVariantConst &params, JsonDocument &response);

    // Getters/Setters
    bool getLedState() const;
    void setLedState(bool state);
};
