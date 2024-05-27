import time
from datetime import datetime
import pytz
import asyncio
from telegram import Bot
from telegram.error import TelegramError

# Configura tu bot token y chat ID
bot_token = 'XXXXXXXXX'
chat_id = 'XXXXXXXXX'

# Inicializa el bot
bot = Bot(token=bot_token)

async def send_alert_message():
    tz = pytz.timezone('America/Bogota')  # Cambia esto a tu zona horaria
    current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    message = f"Se estima que la carretera \"Laboratorio\" presenta fallos, monitoreo realizado a las {current_time}"
    try:
        await bot.send_message(chat_id=chat_id, text=message)
        print("Alerta enviada")
    except TelegramError as e:
        print(f"Error al enviar el mensaje: {e}")

async def send_recovery_message():
    tz = pytz.timezone('America/Bogota')  # Cambia esto a tu zona horaria
    current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    message = f"La carretera \"Laboratorio\" ya se encuentra en óptimas condiciones, monitoreo realizado a las {current_time}"
    try:
        await bot.send_message(chat_id=chat_id, text=message)
        print("Mensaje de recuperación enviado")
    except TelegramError as e:
        print(f"Error al enviar el mensaje: {e}")

# Simulación de condiciones
async def simulate_conditions():
    alert = False
    on = 0
    off = 0
    value = 0

    for _ in range(20):  # Simular 20 lecturas del sensor
        value = int(input("Ingresa un valor simulado del sensor (0-100): "))

        if not alert:
            if value > 20:
                on += 1
                print(f"LED encendido {on} veces")
                if on > 4:
                    alert = True
                    on = 0
                    await send_alert_message()
            else:
                on = 0
        else:
            print("Alerta activa, manteniendo LED 2 encendido")
            if 1 < value < 10:
                off += 1
                print(f"LED apagado {off} veces")
                if off > 10:
                    alert = False
                    off = 0
                    await send_recovery_message()
            else:
                off = 0
        time.sleep(1)

if __name__ == '__main__':
    asyncio.run(simulate_conditions())

