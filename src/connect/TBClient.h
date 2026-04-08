#pragma once
#include <Arduino_MQTT_Client.h>
#include <Server_Side_RPC.h>
#include "../src/config.h"
#include <ThingsBoard.h>
extern Arduino_MQTT_Client mqttClient;
extern Server_Side_RPC<MAX_RPC_SUBS, MAX_RPC_RESP> rpc;
extern ThingsBoard tb;

void tbTask(void *pvParameters);