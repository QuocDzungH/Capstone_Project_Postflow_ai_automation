#ifndef WIFI_CONFIG_H
#define WIFI_CONFIG_H

#include <EEPROM.h>
#include <ArduinoJson.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <WebServer.h>
#include <Adafruit_SHT31.h>

// ===============================
// KHAI BÁO CHÂN
// ===============================

#define LED_PIN  2
#define BTN_PIN  0

#define TRIG_PIN_1 27
#define ECHO_PIN_1 26

#define TRIG_PIN_2 25
#define ECHO_PIN_2 34

#define TRIG_PIN_3 32
#define ECHO_PIN_3 35

#define PUSH_TIME 5000

// ===============================
// BIẾN TOÀN CỤC
// ===============================

WebServer webServer(80);

String ssid;
String password;

/*
  wifiMode:
  0 = ESP32 phát Wi-Fi để cấu hình
  1 = ESP32 đã kết nối Wi-Fi nhà
  2 = ESP32 bị mất Wi-Fi
*/
int wifiMode = 0;

unsigned long blinkTime = 0;
unsigned long lastSerialPrint = 0;


Adafruit_SHT31 sht31 = Adafruit_SHT31();

float currentTemperature = 27.0;
bool sht31Ready = false;

unsigned long lastTempRead = 0;
#define TEMP_READ_INTERVAL 2000

// ===============================
// ĐỌC KHOẢNG CÁCH HC-SR04
// ===============================

float readDistanceCm(uint8_t trigPin, uint8_t echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);

  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  unsigned long duration = pulseIn(echoPin, HIGH, 30000);

  if (duration == 0) {
    return -1;
  }

  float speedOfSound = 331.3 + (0.606 * currentTemperature);
  float speedCmPerUs = speedOfSound / 10000.0;

  return duration * speedCmPerUs / 2.0;
}
float calibrateDistance(int sensorId, float rawDistance) {
  if (rawDistance < 0) {
    return rawDistance;
  }

  switch (sensorId) {
    case 1: return 1.001840 * rawDistance + 0.786248;
    case 2: return 1.001944 * rawDistance + 1.584774;
    case 3: return 1.003323 * rawDistance + 1.507933;
    default: return rawDistance;
  }
}


void updateTemperature() {
  if (!sht31Ready) return;

  if (millis() - lastTempRead >= TEMP_READ_INTERVAL) {
    lastTempRead = millis();

    float temp = sht31.readTemperature();

    if (!isnan(temp)) {
      currentTemperature = temp;
    }
  }
}

// ===============================
// TRANG HIỂN THỊ KHOẢNG CÁCH
// ===============================

const char distancePage[] PROGMEM = R"html(
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ESP32 - 3 cảm biến siêu âm</title>
  <style>
    body {
      margin: 0;
      font-family: Arial, sans-serif;
      background: #f1f5f9;
      text-align: center;
    }
    .container {
      max-width: 900px;
      margin: 45px auto;
      padding: 20px;
    }
    h1 {
      color: #1e293b;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 18px;
      margin-top: 28px;
    }
    .card {
      background: white;
      border-radius: 18px;
      padding: 26px 15px;
      box-shadow: 0 8px 25px rgba(0, 0, 0, 0.12);
    }
    .label {
      font-size: 20px;
      color: #475569;
    }
    .distance {
      margin-top: 18px;
      font-size: 43px;
      font-weight: bold;
      color: #0891b2;
    }
    #status {
      margin-top: 25px;
      font-size: 18px;
      color: #64748b;
    }
    .button {
      display: inline-block;
      margin-top: 25px;
      padding: 12px 20px;
      color: white;
      background: #2563eb;
      text-decoration: none;
      border-radius: 8px;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Khoảng cách từ 3 cảm biến</h1>

    <div class="grid">
      <div class="card">
        <div class="label">Cảm biến 1</div>
        <div id="distance1" class="distance">Đang đo...</div>
      </div>

      <div class="card">
        <div class="label">Cảm biến 2</div>
        <div id="distance2" class="distance">Đang đo...</div>
      </div>

      <div class="card">
        <div class="label">Cảm biến 3</div>
        <div id="distance3" class="distance">Đang đo...</div>
      </div>

      <div class="card">
        <div class="label">Nhiệt độ</div>
        <div id="temperature" class="distance">Đang đo...</div>
      </div>

      <div class="card">
        <div class="label">Thể tích</div>
        <div id="volume" class="distance">Đang đo...</div>
      </div>
    </div>


    <div id="status">Đang kết nối với ESP32</div>


    <a class="button" href="/config">Cấu hình Wi-Fi</a>
  </div>

  <script>
    function showDistance(elementId, success, value) {
      var element = document.getElementById(elementId);

      if (success) {
        element.innerHTML = value.toFixed(1) + " cm";
        element.style.color = "#0891b2";
      } else {
        element.innerHTML = "Không có Echo";
        element.style.color = "#dc2626";
      }
    }

    function updateDistance() {
      fetch("/distance")
        .then(function(response) {
          if (!response.ok) {
            throw new Error("Không nhận được dữ liệu");
          }
          return response.json();
        })
        .then(function(data) {
          showDistance("distance1", data.sensor1.success, data.sensor1.distance);
          showDistance("distance2", data.sensor2.success, data.sensor2.distance);
          showDistance("distance3", data.sensor3.success, data.sensor3.distance);

          document.getElementById("temperature").innerHTML =
            data.temperature.toFixed(1) + " °C";

          document.getElementById("volume").innerHTML =
            data.volume.toFixed(0) + " cm³";
            
          document.getElementById("status").innerHTML =
            "Dữ liệu đang được cập nhật";

          document.getElementById("status").style.color = "#16a34a";
        })
        .catch(function() {
          document.getElementById("status").innerHTML =
            "Không kết nối được với ESP32";

          document.getElementById("status").style.color = "#dc2626";
        });
    }

    updateDistance();
    setInterval(updateDistance, 800);
  </script>
</body>
</html>
)html";

// ===============================
// TRANG CẤU HÌNH WI-FI
// ===============================

const char configPage[] PROGMEM = R"html(
<!DOCTYPE html>
<html lang="vi">

<head>
  <meta charset="UTF-8">

  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >

  <title>Cấu hình Wi-Fi ESP32</title>

  <style>
    body {
      margin: 0;
      font-family: Arial, sans-serif;
      background: #f1f5f9;
    }

    .container {
      max-width: 500px;
      margin: 50px auto;
      padding: 20px;
    }

    .card {
      background: white;
      padding: 30px;
      border-radius: 15px;
      box-shadow: 0 8px 25px rgba(0, 0, 0, 0.12);
    }

    h2 {
      text-align: center;
      color: #1e293b;
    }

    label {
      display: block;
      margin-top: 18px;
      margin-bottom: 8px;
      font-size: 18px;
    }

    select,
    input {
      width: 100%;
      height: 42px;
      padding: 0 10px;
      font-size: 16px;
      box-sizing: border-box;
      border: 1px solid #94a3b8;
      border-radius: 7px;
    }

    button {
      width: 100%;
      height: 45px;
      margin-top: 15px;
      border: none;
      border-radius: 7px;
      font-size: 17px;
      cursor: pointer;
    }

    .save {
      background: #06b6d4;
      color: white;
    }

    .restart {
      background: #f43f5e;
      color: white;
    }

    .distance {
      background: #2563eb;
      color: white;
    }

    #info {
      text-align: center;
      color: #475569;
    }
  </style>
</head>

<body>

  <div class="container">
    <div class="card">

      <h2>Cấu hình Wi-Fi ESP32</h2>

      <p id="info">
        Đang quét mạng Wi-Fi...
      </p>

      <label for="ssid">
        Tên Wi-Fi
      </label>

      <select id="ssid">
        <option value="">
          Đang quét...
        </option>
      </select>

      <label for="password">
        Mật khẩu
      </label>

      <input
        id="password"
        type="password"
        placeholder="Nhập mật khẩu Wi-Fi"
      >

      <button class="save" onclick="saveWifi()">
        Lưu Wi-Fi
      </button>

      <button class="restart" onclick="restartESP()">
        Khởi động lại ESP32
      </button>

      <button class="distance" onclick="openDistancePage()">
        Xem khoảng cách
      </button>

    </div>
  </div>

  <script>
    function scanWifi() {
      fetch("/scanWifi")
        .then(function(response) {
          return response.json();
        })
        .then(function(networks) {
          var select =
            document.getElementById("ssid");

          select.innerHTML = "";

          if (networks.length === 0) {
            var option =
              document.createElement("option");

            option.text =
              "Không tìm thấy Wi-Fi";

            option.value = "";

            select.add(option);
          } else {
            networks.forEach(function(network) {
              var option =
                document.createElement("option");

              option.text = network;
              option.value = network;

              select.add(option);
            });
          }

          document.getElementById("info").innerHTML =
            "Đã quét xong mạng Wi-Fi";
        })
        .catch(function() {
          document.getElementById("info").innerHTML =
            "Không quét được Wi-Fi";
        });
    }

    function saveWifi() {
      var ssid =
        document.getElementById("ssid").value;

      var password =
        document.getElementById("password").value;

      if (ssid === "") {
        alert("Hãy chọn tên Wi-Fi");
        return;
      }

      var url =
        "/saveWifi?ssid=" +
        encodeURIComponent(ssid) +
        "&pass=" +
        encodeURIComponent(password);

      fetch(url)
        .then(function(response) {
          return response.text();
        })
        .then(function(data) {
          alert(data);
        });
    }

    function restartESP() {
      fetch("/restart")
        .then(function(response) {
          return response.text();
        })
        .then(function(data) {
          alert(data);
        });
    }

    function openDistancePage() {
      window.location.href = "/";
    }

    window.onload = scanWifi;
  </script>

</body>
</html>
)html";

// ===============================
// ĐIỀU KHIỂN ĐÈN LED
// ===============================

void blinkLed(unsigned long interval) {
  if (millis() - blinkTime >= interval) {
    digitalWrite(
      LED_PIN,
      !digitalRead(LED_PIN)
    );

    blinkTime = millis();
  }
}

void ledControl() {
  if (wifiMode == 0) {
    // Chế độ cấu hình: nháy nhanh
    blinkLed(150);
  } else if (wifiMode == 1) {
    // Đã kết nối: nháy chậm
    blinkLed(1500);
  } else {
    // Mất kết nối
    blinkLed(400);
  }
}

// ===============================
// SỰ KIỆN WI-FI
// ===============================

void WiFiEvent(WiFiEvent_t event) {
  switch (event) {

    case ARDUINO_EVENT_WIFI_STA_GOT_IP:
      Serial.println();
      Serial.println("Da ket noi Wi-Fi");

      Serial.print("Dia chi IP ESP32: ");
      Serial.println(WiFi.localIP());

      Serial.print("Mo tren PC: http://");
      Serial.println(WiFi.localIP());

      if (MDNS.begin("esp32-buudien")) {
        Serial.println("Da bat mDNS.");
        Serial.println("Truy cap co dinh tai: http://esp32-buudien.local/");
      } else {
        Serial.println("Khong khoi dong duoc mDNS.");
      }

      wifiMode = 1;
      break;

    case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
      Serial.println("ESP32 bi mat ket noi Wi-Fi");

      wifiMode = 2;

      WiFi.reconnect();
      break;

    default:
      break;
  }
}

// ===============================
// THIẾT LẬP WI-FI
// ===============================

void setupWifi() {
  WiFi.onEvent(WiFiEvent); //Nếu Wi-Fi có sự kiện

  if (ssid.length() > 0) {
    Serial.println();
    Serial.print("Dang ket noi Wi-Fi: ");
    Serial.println(ssid);

    WiFi.mode(WIFI_STA);

    WiFi.begin( // start connect
      ssid.c_str(), // change string
      password.c_str()
    );
  } else {
    Serial.println();
    Serial.println(
      "Chua co thong tin Wi-Fi."
    );

    Serial.println(
      "ESP32 dang tao mang Wi-Fi rieng."
    );

    WiFi.mode(WIFI_AP); // access point

    uint8_t macAddress[6];

    WiFi.softAPmacAddress(macAddress); //lấy địa chỉ MAC của ESP32 ghi vào macaddress

    String accessPointName =
      "ESP32-" +
      String(macAddress[4], HEX) +
      String(macAddress[5], HEX);

    accessPointName.toUpperCase();

    WiFi.softAP(accessPointName.c_str()); // phát wifi

    wifiMode = 0;

    Serial.print("Ten Wi-Fi ESP32: ");
    Serial.println(accessPointName);

    Serial.print("Mo trang cau hinh: http://");
    Serial.println(WiFi.softAPIP());
  }
}

// ===============================
// THIẾT LẬP WEB SERVER
// ===============================

void setupWebServer() {
  // Trang chính
  webServer.on("/", HTTP_GET, []() {
    if (wifiMode == 0) {
      webServer.send_P(
        200,
        "text/html",
        configPage  // trang nhập wifi
      );
    } else {
      webServer.send_P(
        200,   // http success
        "text/html", // infor that it's html
        distancePage
      );
    }
  });

  // Trang cấu hình Wi-Fi
  webServer.on("/config", HTTP_GET, []() {
    webServer.send_P(
      200,
      "text/html",
      configPage
    );
  });

  // API trả kết quả khoảng cách của 3 cảm biến
  webServer.on("/distance", HTTP_GET, []() {
    float distance1 = calibrateDistance(1, readDistanceCm(TRIG_PIN_1, ECHO_PIN_1));
    delay(60);

    float distance2 = calibrateDistance(2, readDistanceCm(TRIG_PIN_2, ECHO_PIN_2));
    delay(60);

    float distance3 = calibrateDistance(3, readDistanceCm(TRIG_PIN_3, ECHO_PIN_3));

    DynamicJsonDocument document(512); // Tạo vùng nhớ 512 byte để chứa dữ liệu JSON


    JsonObject sensor1 = document.createNestedObject("sensor1"); // add to json
    sensor1["success"] = distance1 >= 0; // if true
    sensor1["distance"] = distance1 >= 0 ? (105.0 - distance1) : 0;

    JsonObject sensor2 = document.createNestedObject("sensor2");
    sensor2["success"] = distance2 >= 0;
    sensor2["distance"] = distance2 >= 0 ? (105.0 - distance2) : 0;

    JsonObject sensor3 = document.createNestedObject("sensor3");
    sensor3["success"] = distance3 >= 0;
    sensor3["distance"] = distance3 >= 0 ? (105.0 - distance3) : 0;

    document["temperature"] = currentTemperature;
    float edge1 = distance1 >= 0 ? (105.0 - distance1) : 0;
    float edge2 = distance2 >= 0 ? (105.0 - distance2) : 0;
    float edge3 = distance3 >= 0 ? (105.0 - distance3) : 0;
    // JsonObject sensor1 = document.createNestedObject("sensor1");
    // sensor1["success"] = distance1 >= 0;
    // sensor1["distance"] = distance1 >= 0 ? distance1 : 0;

    // JsonObject sensor2 = document.createNestedObject("sensor2");
    // sensor2["success"] = distance2 >= 0;
    // sensor2["distance"] = distance2 >= 0 ? distance2 : 0;

    // JsonObject sensor3 = document.createNestedObject("sensor3");
    // sensor3["success"] = distance3 >= 0;
    // sensor3["distance"] = distance3 >= 0 ? distance3 : 0;

    // document["temperature"] = currentTemperature;
    // float edge1 = distance1 >= 0 ? distance1 : 0;
    // float edge2 = distance2 >= 0 ? distance2 : 0;
    // float edge3 = distance3 >= 0 ? distance3 : 0;
    document["volume"] = (distance1 >= 0 && distance2 >= 0 && distance3 >= 0)
      ? edge1 * edge2 * edge3
      : 0;
    String jsonResult;
    serializeJson(document, jsonResult);  // change JSON thành chuỗi

    webServer.send(
      200,
      "application/json",
      jsonResult
    );
  });

  // Quét danh sách Wi-Fi
  webServer.on("/scanWifi", HTTP_GET, []() {
    Serial.println("Dang quet Wi-Fi...");

    int networkCount =
      WiFi.scanNetworks(false, true); // lưu so luong wifi

    DynamicJsonDocument document(1024);

    for (int i = 0; i < networkCount; i++) {
      String networkName = WiFi.SSID(i);

      bool alreadyExists = false;

      for (JsonVariant item : document.as<JsonArray>()) {  // check teen wifi da duoc luu de so sanh
        if (item.as<String>() == networkName) {
          alreadyExists = true;
          break;
        }
      }

      if (
        !alreadyExists &&
        networkName.length() > 0
      ) {
        document.add(networkName);
      }
    }

    String wifiList;

    serializeJson( // chuyen json thanh str
      document,
      wifiList
    );

    WiFi.scanDelete();

    webServer.send(
      200,
      "application/json",
      wifiList
    );
  });

  // Lưu tên và mật khẩu Wi-Fi
  webServer.on("/saveWifi", HTTP_GET, []() {
    String newSSID =
      webServer.arg("ssid");

    String newPassword =
      webServer.arg("pass");

    if (newSSID.length() == 0) {
      webServer.send(
        400,
        "text/plain",
        "Ten Wi-Fi khong duoc de trong"
      );

      return;
    }

    EEPROM.writeString(
      0,
      newSSID
    );

    EEPROM.writeString( // Ghi mật khẩu vào EEPROM ở loc.
      32,
      newPassword
    );

    bool saved = EEPROM.commit();  // Lưu thay đổi thật sự vào bộ nhớ Flash

    if (saved) {
      ssid = newSSID;
      password = newPassword;

      Serial.print("Da luu Wi-Fi: ");
      Serial.println(ssid);

      webServer.send(
        200,
        "text/plain",
        "Da luu Wi-Fi. Hay bam khoi dong lai ESP32."
      );
    } else {
      webServer.send(
        500,
        "text/plain",
        "Khong luu duoc Wi-Fi"
      );
    }
  });

  // Khởi động lại ESP32
  webServer.on("/restart", HTTP_GET, []() {
    webServer.send(
      200,
      "text/plain",
      "ESP32 dang khoi dong lai..."
    );

    delay(1000);

    ESP.restart();
  });

  // Trường hợp nhập sai địa chỉ
  webServer.onNotFound([]() {
    webServer.send(
      404,
      "text/plain",
      "Khong tim thay duong dan"
    );
  });

  webServer.begin();

  Serial.println(
    "WebServer da khoi dong o cong 80"
  );
}

// ===============================
// GIỮ NÚT BOOT ĐỂ XÓA WI-FI
// ===============================

void checkButton() {
  static bool buttonPressed = false; //start
  static unsigned long pressStartTime = 0; //begin with 0

  if (digitalRead(BTN_PIN) == LOW) {
    if (!buttonPressed) {
      buttonPressed = true;
      pressStartTime = millis();

      Serial.println(
        "Dang giu nut BOOT..."
      );
    }

    if (
      buttonPressed &&
      millis() - pressStartTime >= PUSH_TIME
    ) {
      Serial.println(
        "Dang xoa thong tin Wi-Fi..."
      );

      for (int i = 0; i < 100; i++) {
        EEPROM.write(i, 0); // Duyệt qua 100 ô nhớ EEPROM and ddef 0
      }

      EEPROM.commit();

      Serial.println(
        "Da xoa Wi-Fi. ESP32 dang khoi dong lai."
      );

      delay(1000);

      ESP.restart();
    }
  } else {
    buttonPressed = false;
  }
}

// ===============================
// CLASS WIFI CONFIG
// ===============================

class Config {
public:
  void begin() {
    pinMode(LED_PIN, OUTPUT);
    pinMode(BTN_PIN, INPUT_PULLUP);

    pinMode(TRIG_PIN_1, OUTPUT);
    pinMode(ECHO_PIN_1, INPUT);

    pinMode(TRIG_PIN_2, OUTPUT);
    pinMode(ECHO_PIN_2, INPUT);

    pinMode(TRIG_PIN_3, OUTPUT);
    pinMode(ECHO_PIN_3, INPUT);

    digitalWrite(TRIG_PIN_1, LOW);
    digitalWrite(TRIG_PIN_2, LOW);
    digitalWrite(TRIG_PIN_3, LOW);
    digitalWrite(LED_PIN, LOW);

    EEPROM.begin(100);
    Wire.begin();

    if (sht31.begin(0x44)) {
      sht31Ready = true;
      Serial.println("Da tim thay SHT31");
    } else {
      sht31Ready = false;
      Serial.println("Khong tim thay SHT31, dung nhiet do mac dinh 25C");
    }
    ssid = EEPROM.readString(0);
    password = EEPROM.readString(32);

    if (ssid != "") {  // Nếu EEPROM có lưu tên Wi-Fi
      Serial.println("Wifi name: " + ssid);
      // Wi-Fi passwords are not printed to the serial console.
    }

    setupWifi();//start

    // Luôn bật WebServer
    setupWebServer();
  }

  void run() {
    updateTemperature();
    webServer.handleClient(); // Kiểm tra và xử lý yêu cầu từ trình duyệt

    checkButton(); // keep booot
    ledControl(); // led should be

    if (millis() - lastSerialPrint >= 1000) {
      lastSerialPrint = millis();

      float distance1 = readDistanceCm(TRIG_PIN_1, ECHO_PIN_1);
      delay(60);

      float distance2 = readDistanceCm(TRIG_PIN_2, ECHO_PIN_2);
      delay(60);

      float distance3 = readDistanceCm(TRIG_PIN_3, ECHO_PIN_3);

      Serial.print("CB1: ");
      if (distance1 < 0) {
        Serial.print("Khong Echo");
      } else {
        Serial.print(distance1, 1);
        Serial.print(" cm");
      }

      Serial.print(" | CB2: ");
      if (distance2 < 0) {
        Serial.print("Khong Echo");
      } else {
        Serial.print(distance2, 1);
        Serial.print(" cm");
      }

      Serial.print(" | CB3: ");
      if (distance3 < 0) {
        Serial.print("Khong Echo");
      } else {
        Serial.print(distance3, 1);
        Serial.print(" cm");
      }

      Serial.println();
    }

    delay(2);
  }
};

Config wifiConfig;
#endif  // WIFI_CONFIG_H