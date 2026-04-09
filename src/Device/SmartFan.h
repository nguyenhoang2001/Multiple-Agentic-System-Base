#pragma once
#include "BaseDevice.h"

class SmartFan : public BaseDevice {
private:
    int controlPin;
    int speed;

public:
    SmartFan(const char* name, const char* token, const char* id, int pin);
    ~SmartFan();

    void process() override;

    // RPC handlers
    void onSetSpeed(const JsonVariantConst &params, JsonDocument &response);
    void onSetToggle(const JsonVariantConst &params, JsonDocument &response);

    // Getters/Setters
    int getSpeed() const;
    void setSpeed(int speedLevel);
};
