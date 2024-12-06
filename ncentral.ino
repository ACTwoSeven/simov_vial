#include "LoRaWan_APP.h"
#include "Arduino.h"

// Configuración de Radio LoRa
#define RF_FREQUENCY 915000000
#define TX_OUTPUT_POWER        5          // dBm
#define LORA_BANDWIDTH         0          // 125 kHz
#define LORA_SPREADING_FACTOR  7
#define LORA_CODINGRATE        1          // 4/5
#define LORA_PREAMBLE_LENGTH   8
#define LORA_SYMBOL_TIMEOUT    0
#define BUFFER_SIZE            30

#define SERIAL_TIMEOUT         10         // Tiempo de espera para lectura serial en ms

// Variables globales
uint8_t serialBuffer[256];  // Buffer para recibir datos seriales
int serialSize;             // Tamaño de datos recibidos

char txpacket[BUFFER_SIZE];
char rxpacket[BUFFER_SIZE];
static RadioEvents_t RadioEvents;
int16_t Rssi, rxSize;

// Estados del dispositivo
typedef enum {
    LOWPOWER,
    RX,
    TX
} States_t;

States_t state = RX;
uint8_t targetNode = 0;  // Nodo al que queremos activar (0 = ninguno)
bool needToActivate = false;  // Flag para indicar si necesitamos activar un nodo

// Prototipos de funciones
void OnTxDone(void);
void OnTxTimeout(void);
void OnRxDone(uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr);

void setup() {
    Serial.begin(115200);
    Serial.println("Central Node Starting...");
    
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
    
    // Iniciar en modo RX
    state = RX;
    Radio.Rx(0); // Iniciar en modo de recepción
}

void loop() {
    // Procesar lectura serial siempre que haya datos disponibles
    serialSize = Serial.read(serialBuffer, SERIAL_TIMEOUT);
    if (serialSize > 0) {
        Serial.printf("Received data size %d: ", serialSize);
        Serial.write(serialBuffer, serialSize);
        Serial.println();

        // Procesar el comando recibido
        if (serialSize == 2 && serialBuffer[0] == 'A') {
            targetNode = serialBuffer[1] - '0';
            if (targetNode > 0 && targetNode <= 9) {
                needToActivate = true;
                state = TX;
                Serial.printf("Will activate node %d\n", targetNode);
            }
        }
        
    }

    // Manejar estados de LoRa
    switch (state) {
        case TX:
            if (needToActivate) {
                sprintf(txpacket, "A%d", targetNode);
                
                Serial.printf("\r\nSending activation to node %d: \"%s\"\r\n", 
                              targetNode, txpacket);
                
                Radio.Send((uint8_t *)txpacket, strlen(txpacket));
                needToActivate = false;
            }
            state = LOWPOWER;
            break;
            
        case RX:
            // Siempre permanecer en RX después de recibir o transmitir
            Radio.Rx(0);
            state = LOWPOWER;
            break;
            
        case LOWPOWER:
            // Bajo consumo, pero mantener el procesamiento del Serial
            break;
            
        default:
            break;
    }
    // Procesar las interrupciones de la radio
    Radio.IrqProcess();
}

// Callbacks de eventos LoRa
void OnTxDone(void) {
    Serial.println("TX done");
    state = RX;  // Volver a modo recepción
}

void OnTxTimeout(void) {
    Radio.Sleep();
    Serial.println("TX Timeout");
    state = RX;  // Volver a modo recepción
}

void OnRxDone(uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr) {
    Rssi = rssi;
    rxSize = size;
    memcpy(rxpacket, payload, size);
    rxpacket[size] = '\0';
    
    
    
    if (rxpacket[0] == 'N') {
        int nodeId = rxpacket[1] - '0';
        int value = atoi(rxpacket + 3);  // Saltar "N1:"
        Serial.printf("\r%s\r\n",
                 rxpacket);
    }
    else if (rxpacket[0] == 'D') {
        int nodeId = rxpacket[3] - '0';
        int value = atoi(rxpacket + 3);  // Saltar "N1:"
        Serial.printf("\r%s\r\n", rxpacket);
    }

    state = RX; // Seguir escuchando
}