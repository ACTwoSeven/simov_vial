#include <WiFi.h>
#include <UniversalTelegramBot.h>
#include <WiFiClientSecure.h>

// Configura tus credenciales de Wi-Fi
const char* ssid = "USTA_Estudiantes";
const char* password = "#soytomasino";

// Configura tu token de bot de Telegram y chat ID
#define BOT_TOKEN "7286163016:XXXXXX"
#define CHAT_ID "-1002XXXXXXXXX"

// Pines para los LEDs
const int LED_PIN_1 = 2;
const int LED_PIN_2 = 4;
int on = 0;
int off = 0;
bool alert = false;

// Rangos de valores para activar los LEDs
const int LED_THRESHOLD_1 = 1;
const int LED_THRESHOLD_2 = 20;

// Inicializa el objeto WiFiClientSecure
WiFiClientSecure client;
UniversalTelegramBot bot(BOT_TOKEN, client);

// Función para enviar un mensaje de alerta a Telegram
void sendAlertMessage() {
  String message = "Se estima que la carretera \"Laboratorio\" presenta fallos, monitoreo realizado a las " + String(millis());
  bot.sendMessage(CHAT_ID, message, "");
  Serial.println("Alerta enviada");
}

// Función para enviar un mensaje de recuperación a Telegram
void sendRecoveryMessage() {
  String message = "La carretera \"Laboratorio\" ya se encuentra en óptimas condiciones, monitoreo realizado a las " + String(millis());
  bot.sendMessage(CHAT_ID, message, "");
  Serial.println("Mensaje de recuperación enviado");
}

void setup() {
  Serial.begin(115200);

  // Conéctate a Wi-Fi
  WiFi.begin(ssid, password);
  Serial.print("Conectando a Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Conectado a la red Wi-Fi ");
  Serial.println(ssid);

  // Configura los pines de los LEDs
  pinMode(LED_PIN_1, OUTPUT);
  pinMode(LED_PIN_2, OUTPUT);

  // Configura el cliente para Telegram
  client.setInsecure(); // Esto desactiva la verificación del certificado SSL
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    // Lee del puerto analógico
    int sensorValue = analogRead(32);
    Serial.print("Valor del sensor: ");
    Serial.println(sensorValue);

    // Activa los LEDs según los valores leídos
    if (!alert) {
      if (sensorValue > LED_THRESHOLD_2) {
        digitalWrite(LED_PIN_1, HIGH);
        digitalWrite(LED_PIN_2, LOW);
        on++;
      } else if (sensorValue > LED_THRESHOLD_1) {
        digitalWrite(LED_PIN_1, HIGH);
        digitalWrite(LED_PIN_2, LOW);
        off++;
      } else {
        digitalWrite(LED_PIN_1, LOW);
        digitalWrite(LED_PIN_2, LOW);
      }

      // Verifica si se debe enviar una alerta
      if (on > 4) {
        sendAlertMessage();
        alert = true;
        on = 0;
      }
    } else {
      // Mantiene LED 2 encendido durante la alerta
      digitalWrite(LED_PIN_1, LOW);
      digitalWrite(LED_PIN_2, HIGH);

      if (sensorValue < LED_THRESHOLD_1) {
        off++;
        if (off > 10) {
          sendRecoveryMessage();
          alert = false;
          off = 0;
        }
      } else {
        on = 0;
      }
    }

  } else {
    Serial.println("No se pudo conectar a Wi-Fi");
  }

  delay(1000); // Espera 1 segundo antes de leer el sensor nuevamente
}



