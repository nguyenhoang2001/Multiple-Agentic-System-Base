#pragma once

constexpr char     WIFI_SSID[]          = "ACLAB";
constexpr char     WIFI_PASSWORD[]      = "ACLAB2023";
constexpr char     TOKEN[]              = "xdF2nW4aR9SAdqqPiym0";
constexpr char     DEVICE_ID[]          = "fcceeaa0-3111-11f1-9981-cffbb69f5b14";
constexpr char     THINGSBOARD_SERVER[] = "app.coreiot.io";
constexpr uint16_t THINGSBOARD_PORT     = 1883U;
constexpr uint32_t SERIAL_BAUD          = 115200U;

constexpr int LED_PIN = 48;

constexpr char    LED_KEY[]       = "led";
constexpr char    RPC_SET_VALUE[] = "setValue";
constexpr uint8_t MAX_RPC_SUBS   = 1U;
constexpr uint8_t MAX_RPC_RESP   = 1U;

constexpr uint16_t MAX_MSG_SIZE = 512U;