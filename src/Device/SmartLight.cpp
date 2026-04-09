#include "SmartLight.h"
#include <Arduino.h>

SmartLight::SmartLight(const char* name, const char* token, const char* id, int pin)
    : BaseDevice(name, token, id, "smart_light"), ledPin(pin), ledState(false) {
    
    // Initialize attributes
    initializeAttribute("led", "boolean");
    initializeAttribute("brightness", "integer");
    
    // Setup GPIO
    pinMode(ledPin, OUTPUT);
    digitalWrite(ledPin, LOW);
    
    // Register RPC handlers
    registerRPCHandler("setValue", [this](const JsonVariantConst &params, JsonDocument &response) {
        this->onSetValue(params, response);
    });
    
    registerRPCHandler("setBrightness", [this](const JsonVariantConst &params, JsonDocument &response) {
        this->onSetBrightness(params, response);
    });
    
    Serial.printf("[SmartLight] Initialized: %s on pin %d\n", name, pin);
}

SmartLight::~SmartLight() {
    digitalWrite(ledPin, LOW);
}

void SmartLight::process() {
    // Process pending tasks
    // This is called periodically from the device task
}

void SmartLight::onSetValue(const JsonVariantConst &params, JsonDocument &response) {
    if (!params["led"].is<bool>()) {
        response["error"] = "missing key 'led'";
        return;
    }
    
    bool newState = params["led"].as<bool>();
    setLedState(newState);
    response["led"] = newState;
    
    Serial.printf("[SmartLight] %s: led set to %s\n", getName(), newState ? "ON" : "OFF");
}

void SmartLight::onSetBrightness(const JsonVariantConst &params, JsonDocument &response) {
    if (!params["brightness"].is<int>()) {
        response["error"] = "missing key 'brightness'";
        return;
    }
    
    int brightness = params["brightness"].as<int>();
    if (brightness < 0 || brightness > 255) {
        response["error"] = "brightness must be 0-255";
        return;
    }
    
    setAttribute("brightness", brightness);
    markAttributePending("brightness");
    response["brightness"] = brightness;
    
    // TODO: Implement PWM for brightness control
    Serial.printf("[SmartLight] %s: brightness set to %d\n", getName(), brightness);
}

bool SmartLight::getLedState() const {
    return ledState;
}

void SmartLight::setLedState(bool state) {
    if (ledState != state) {
        ledState = state;
        digitalWrite(ledPin, state ? HIGH : LOW);
        setAttribute("led", state);
        markAttributePending("led");
    }
}
