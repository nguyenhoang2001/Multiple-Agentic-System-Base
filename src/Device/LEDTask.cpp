#include "LEDTask.h"
#include "DeviceManager.h"
#include <Arduino.h>

void deviceTask(void *pvParameters) {
    Serial.println("[DeviceTask] Started");
    
    DeviceManager* dm = DeviceManager::getInstance();
    dm->printDevicesInfo();
    
    for (;;) {
        // Process all devices
        dm->processAll();
        
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}