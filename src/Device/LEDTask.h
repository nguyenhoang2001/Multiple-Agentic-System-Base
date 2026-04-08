#pragma once
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

extern QueueHandle_t ledQueue;
extern volatile bool ledState;
extern volatile bool pendingAttrUpdate;

void ledTask(void *pvParameters);