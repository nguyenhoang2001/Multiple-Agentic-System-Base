#include "SmartFan.h"
#include <Arduino.h>

SmartFan::SmartFan(const char* name, const char* token, const char* id, int pin)
    : BaseDevice(name, token, id, "smart_fan"), controlPin(pin), speed(0) {
    
    // Initialize attributes
    initializeAttribute("speed", "integer");
    initializeAttribute("toggle", "boolean");
    
    // Setup GPIO
    pinMode(controlPin, OUTPUT);
    digitalWrite(controlPin, LOW);
    
    // Register RPC handlers
    registerRPCHandler("setSpeed", [this](const JsonVariantConst &params, JsonDocument &response) {
        this->onSetSpeed(params, response);
    });
    
    registerRPCHandler("setToggle", [this](const JsonVariantConst &params, JsonDocument &response) {
        this->onSetToggle(params, response);
    });
    
    Serial.printf("[SmartFan] Initialized: %s on pin %d\n", name, pin);
}

SmartFan::~SmartFan() {
    digitalWrite(controlPin, LOW);
}

void SmartFan::process() {
    // Process pending tasks
    // This is called periodically from the device task
}

void SmartFan::onSetSpeed(const JsonVariantConst &params, JsonDocument &response) {
    if (!params["speed"].is<int>()) {
        response["error"] = "missing key 'speed'";
        return;
    }
    
    int speedLevel = params["speed"].as<int>();
    if (speedLevel < 0 || speedLevel > 3) {
        response["error"] = "speed must be 0-3";
        return;
    }
    
    setSpeed(speedLevel);
    response["speed"] = speedLevel;
    
    Serial.printf("[SmartFan] %s: speed set to %d\n", getName(), speedLevel);
}

void SmartFan::onSetToggle(const JsonVariantConst &params, JsonDocument &response) {
    if (!params["toggle"].is<bool>()) {
        response["error"] = "missing key 'toggle'";
        return;
    }
    
    bool isOn = params["toggle"].as<bool>();
    setSpeed(isOn ? 1 : 0);  // Set to speed 1 if on, 0 if off
    response["toggle"] = isOn;
    
    Serial.printf("[SmartFan] %s: toggle %s\n", getName(), isOn ? "ON" : "OFF");
}

int SmartFan::getSpeed() const {
    return speed;
}

void SmartFan::setSpeed(int speedLevel) {
    if (speed != speedLevel) {
        speed = speedLevel;
        
        // TODO: Implement PWM control for different speed levels
        if (speed == 0) {
            digitalWrite(controlPin, LOW);
        } else {
            digitalWrite(controlPin, HIGH);
        }
        
        setAttribute("speed", speedLevel);
        setAttribute("toggle", speedLevel > 0);
        markAttributePending();
    }
}
