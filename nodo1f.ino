#include "LoRaWan_APP.h"
#include "Arduino.h"
#ifndef LoraWan_RGB
#define LoraWan_RGB 0
#endif
// Configuración de Radio LoRa
#define RF_FREQUENCY 915000000
#define TX_OUTPUT_POWER        5          // dBm
#define LORA_BANDWIDTH        0           // 125 kHz
#define LORA_SPREADING_FACTOR 7
#define LORA_CODINGRATE      1           // 4/5
#define LORA_PREAMBLE_LENGTH 8
#define LORA_SYMBOL_TIMEOUT  0
#define BUFFER_SIZE          30
// Configuración del nodo
const uint8_t NODE_ID = 3;           // ID único del nodo
const uint16_t THRESHOLD = 100;      // Valor umbral del sensor
const uint8_t THRESHOLD_COUNT = 10;   // Veces que debe superarse el umbral
const uint32_t TIME_WINDOW = 60000;  // Ventana de tiempo (1 min)
const int ADC_PIN = ADC;             // Pin ADC para el sensor

// Variables globales
char txpacket[BUFFER_SIZE];
char rxpacket[BUFFER_SIZE];
static RadioEvents_t RadioEvents;
int16_t Rssi, rxSize;
uint8_t thresholdExceededCount = 0;
uint32_t firstThresholdTime = 0;

// Estados del dispositivo
typedef enum {
    LOWPOWER,
    RX,
    TX
} States_t;

States_t state;
bool isActivated = false;
bool desactivar = false;
void OnTxDone(void);
void OnTxTimeout(void);
void OnRxDone(uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr);

void setup() {
    Serial.begin(115200);
    Serial.println("Iniciando nodo LoRa...");
    
    // Configurar eventos de radio
    RadioEvents.TxDone = OnTxDone;
    RadioEvents.TxTimeout = OnTxTimeout;
    RadioEvents.RxDone = OnRxDone;

    // Inicializar radio
    Radio.Init(&RadioEvents);
    Radio.SetChannel(RF_FREQUENCY);
    
    // Configurar TX
    Radio.SetTxConfig(MODEM_LORA, TX_OUTPUT_POWER, 0, LORA_BANDWIDTH,
                     LORA_SPREADING_FACTOR, LORA_CODINGRATE,
                     LORA_PREAMBLE_LENGTH, false,
                     true, 0, 0, false, 3000);

    // Configurar RX
    Radio.SetRxConfig(MODEM_LORA, LORA_BANDWIDTH, LORA_SPREADING_FACTOR,
                     LORA_CODINGRATE, 0, LORA_PREAMBLE_LENGTH,
                     LORA_SYMBOL_TIMEOUT, false,
                     0, true, 0, 0, false, true);

    // Configurar pin ADC
    pinMode(ADC_PIN, INPUT);
    
    // Iniciar en modo RX esperando activación
    state = RX;
}

void loop() {
    switch(state) {
        case TX:
            if (isActivated) {
                int sensorValue = readSensor();
                
                // Verificar umbral
                if (sensorValue > THRESHOLD) {
                    if (thresholdExceededCount == 0) {
                        firstThresholdTime = millis();
                    }
                    
                    thresholdExceededCount++;
                    
                    if (thresholdExceededCount >= THRESHOLD_COUNT) {
                        if ((millis() - firstThresholdTime) <= TIME_WINDOW) {
                            isActivated = false;
                            Serial.println("Threshold exceeded, returning to RX mode");
                            desactivar=true;
                            sprintf(txpacket, "DN:%d", NODE_ID);
                            Serial.printf("\r\nSending packet \"%s\", length %d\r\n", 
                            txpacket, strlen(txpacket));
                            Radio.Send((uint8_t *)txpacket, strlen(txpacket));
                            break;
                        } else {
                            thresholdExceededCount = 1;
                            firstThresholdTime = millis();
                        }
                    }
                }
                
                // Preparar paquete
                sprintf(txpacket, "N%d:%d", NODE_ID, sensorValue);
                turnOnRGB(COLOR_SEND, 0);
                
                Serial.printf("\r\nSending packet \"%s\", length %d\r\n", 
                            txpacket, strlen(txpacket));
                
                Radio.Send((uint8_t *)txpacket, strlen(txpacket));
            }
            state = LOWPOWER;
            break;
            
        case RX:
            Serial.println("Into RX mode");
            Radio.Rx(0);
            state = LOWPOWER;
            break;
            
        case LOWPOWER:
            lowPowerHandler();
            break;
            
        default:
            break;
    }
    Radio.IrqProcess();
}

void OnTxDone(void) {
    Serial.println("TX done");
    turnOnRGB(0, 0);
    delay(1000); // Pequeña pausa entre transmisiones
    if(desactivar){
      state = RX;
    }else{
      state = TX;  // Continuar transmitiendo mientras esté activado
    }
    
}

void OnTxTimeout(void) {
    Radio.Sleep();
    Serial.println("TX Timeout");
    state = TX;
}

void OnRxDone(uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr) {
    Rssi = rssi;
    rxSize = size;
    memcpy(rxpacket, payload, size);
    rxpacket[size] = '\0';
    
    turnOnRGB(COLOR_RECEIVED, 0);
    Radio.Sleep();

    Serial.printf("\r\nReceived packet \"%s\" with Rssi %d, length %d\r\n",
                 rxpacket, Rssi, rxSize);

    // Verificar si es comando de activación
    if (size >= 2 && rxpacket[0] == 'A' && (rxpacket[1] - '0') == NODE_ID) {
        Serial.println("Node activated!");
        isActivated = true;
        desactivar = false;
        thresholdExceededCount = 0;
        firstThresholdTime = 0;
        state = TX;
    } else {
        Serial.println("Command not recognized or not for this node");
        state = RX; // Seguir escuchando si no es para este nodo
    }
}

int readSensor() {
    int sensorValue = analogRead(ADC_PIN);
    delay(50);  // Estabilidad entre lecturas
    Serial.printf("Sensor value read: %d\n", sensorValue);
    return sensorValue;
}
