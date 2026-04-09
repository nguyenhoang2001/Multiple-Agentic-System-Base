# Device Manager - Hướng dẫn sử dụng

## Tổng quan

Hệ thống Device Manager cho phép quản lý nhiều loại thiết bị (đèn, quạt, v.v.) một cách linh hoạt.

## Cấu trúc

```
Device/
├── IDevice.h              # Interface chung cho tất cả thiết bị
├── BaseDevice.h/cpp       # Lớp cơ sở (chứa logic chung)
├── SmartLight.h/cpp       # Thiết bị đèn thông minh
├── SmartFan.h/cpp         # Thiết bị quạt thông minh
├── DeviceManager.h/cpp    # Quản lý tất cả thiết bị
└── LEDTask.h/cpp          # Task xử lý thiết bị (chạy trên FreeRTOS)
```

## Cách sử dụng

### 1. Thêm thiết bị trong main.cpp

```cpp
DeviceManager* dm = DeviceManager::getInstance();

// Thêm đèn
dm->registerDevice(std::make_shared<SmartLight>(
    "Đèn trần",                    // Tên
    TOKEN,                         // Token ThingsBoard
    DEVICE_ID,                     // Device ID
    LED_PIN                        // GPIO pin
));

// Thêm quạt
dm->registerDevice(std::make_shared<SmartFan>(
    "quạt trần",
    TOKEN,
    DEVICE_ID,
    47  // GPIO pin
));
```

### 2. Tạo loại thiết bị mới

**Bước 1:** Tạo class kế thừa từ `BaseDevice`

```cpp
// SmartDoor.h
#pragma once
#include "BaseDevice.h"

class SmartDoor : public BaseDevice {
private:
    int sensorPin;
    bool isOpen;

public:
    SmartDoor(const char* name, const char* token, const char* id, int pin);
    void process() override;
    void onSetLock(const JsonVariantConst &params, JsonDocument &response);
};
```

**Bước 2:** Triển khai các phương thức

```cpp
// SmartDoor.cpp
#include "SmartDoor.h"

SmartDoor::SmartDoor(const char* name, const char* token, const char* id, int pin)
    : BaseDevice(name, token, id, "smart_door"), sensorPin(pin), isOpen(false) {
    
    // Khởi tạo attribute
    initializeAttribute("isOpen", "boolean");
    initializeAttribute("locked", "boolean");
    
    // Setup GPIO
    pinMode(sensorPin, INPUT);
    
    // Đăng ký RPC handler
    registerRPCHandler("setLock", [this](const JsonVariantConst &params, JsonDocument &response) {
        this->onSetLock(params, response);
    });
}

void SmartDoor::process() {
    // Xử lý logic thiết bị định kỳ
}

void SmartDoor::onSetLock(const JsonVariantConst &params, JsonDocument &response) {
    if (!params.containsKey("locked")) {
        response["error"] = "missing key 'locked'";
        return;
    }
    bool shouldLock = params["locked"].as<bool>();
    // ... Logic khóa cửa
    response["locked"] = shouldLock;
}
```

## Các phương thức chính

### DeviceManager

```cpp
DeviceManager* dm = DeviceManager::getInstance();

// Đăng ký thiết bị
dm->registerDevice(device);

// Lấy thiết bị theo ID
IDevice* device = dm->getDevice("device_id");

// Lấy thiết bị theo tên
IDevice* device = dm->getDeviceByName("Đèn trần");

// Xử lý RPC
dm->handleRPC(deviceId, method, params, response);

// Lấy tất cả attribute đang chờ đồng bộ
JsonObject pending = dm->getAllPendingAttributes();

// Xóa cờ đang chờ
dm->clearAllPendingFlags();

// Xử lý tất cả thiết bị
dm->processAll();
```

### IDevice

```cpp
// Lấy thông tin thiết bị
const char* name = device->getName();
const char* type = device->getType();
const char* token = device->getDeviceToken();
const char* id = device->getDeviceId();

// Quản lý attribute
JsonObject attrs = device->getAttributes();  // Lấy tất cả attribute
JsonVariant value = device->getAttribute("led");  // Lấy 1 attribute
device->setAttribute("led", true);  // Cập nhật attribute

// RPC
device->registerRPCHandler("setValue", handler);  // Đăng ký handler
device->handleRPC("setValue", params, response);  // Xử lý RPC

// Pending attributes
device->markAttributePending();  // Đánh dấu để đồng bộ
device->markAttributePending("led");  // Đánh dấu 1 attribute
JsonObject pending = device->getPendingAttributes();
device->clearPendingFlags();  // Xóa cờ
```

## RPC Call từ ThingsBoard

ThingsBoard gửi RPC theo format:

```json
{
  "method": "setValue",
  "params": {
    "led": true
  }
}
```

Hệ thống sẽ:
1. Nhận RPC từ ThingsBoard
2. Tìm device theo `DEVICE_ID`
3. Gọi handler tương ứng
4. Gửi response lại

## Ví dụ JSON YAML → C++

**YAML (cấu hình):**
```yaml
rooms:
  - name: living_room
    devices:
      - name: Đèn trần
        device_id: fcceeaa0-3111-11f1-9981-cffbb69f5b14
        type: smart_light
        attributes:
          - name: led
            type: boolean
```

**C++ (setup):**
```cpp
dm->registerDevice(std::make_shared<SmartLight>(
    "Đèn trần",
    TOKEN,
    "fcceeaa0-3111-11f1-9981-cffbb69f5b14",
    LED_PIN
));
```

## Debugging

Xem thông tin tất cả thiết bị đã đăng ký:

```cpp
DeviceManager::getInstance()->printDevicesInfo();
```

Output:
```
[DeviceManager] Registered Devices:
Total: 2 devices
  - Name: Đèn trần
    Type: smart_light
    ID: fcceeaa0-3111-11f1-9981-cffbb69f5b14
    Token: xdF2nW4aR9SAdqqPiym0
  - Name: quạt trần
    Type: smart_fan
    ID: fcceeaa0-3111-11f1-9981-cffbb69f5b14
    Token: xdF2nW4aR9SAdqqPiym0
```

## Next Steps

Bạn muốn:
1. ✅ Tạo hệ thống thiết bị chung (hoàn tất)
2. ⏳ Thêm thiết bị mới từ YAML bằng script Python?
3. ⏳ Quản lý nhiều device_ids khác nhau?
4. ⏳ Thêm storage (SPIFFS) để lưu trạng thái thiết bị?
