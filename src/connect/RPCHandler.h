#pragma once
#include <ArduinoJson.h>
#include "../config.h"

// Handle RPC call from ThingsBoard
void handleRPCCall(const char* method, const char* params, std::string& response);