import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont
import serial
import serial.tools.list_ports
import threading
import time
from typing import Dict, Optional
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import numpy as np
import firebase_admin
from firebase_admin import credentials, firestore
from telegram import Bot
import asyncio
from telegram.ext import ApplicationBuilder
import os
from dotenv import load_dotenv
import tweepy

load_dotenv()

TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
TWITTER_API_SECRET_KEY = os.getenv('TWITTER_API_SECRET_KEY')
TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

# Inicializar la app de Firebase con las credenciales
cred = credentials.Certificate('serviceAccountKey.json')
firebase_admin.initialize_app(cred)

# Obtener referencia a la base de datos Firestore
db = firestore.client()

class LoRaNodeManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Gestor de Nodos LoRa")
        self.root.geometry("1000x700")
        self.root.minsize(1000, 700)

        # Aplicar estilo
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Fuentes personalizadas
        self.title_font = tkfont.Font(family='Helvetica', size=16, weight='bold')
        self.normal_font = tkfont.Font(family='Helvetica', size=10)

        # Variables de estado
        self.nodes: Dict[str, bool] = {}  # {node_id: is_active}
        self.serial_port: Optional[serial.Serial] = None
        self.is_monitoring = False
        self.monitor_thread = None

        # Datos para la gráfica por nodo
        self.sensor_data: Dict[str, list] = {}  # {node_id: [sensor_values]}
        self.time_data: Dict[str, list] = {}    # {node_id: [timestamps]}
        self.lines: Dict[str, any] = {}         # {node_id: line_object}

        # Configuración de la interfaz
        self.setup_gui()

        # Cargar puertos disponibles
        self.update_available_ports()

        # Agregar paleta de colores para los nodos
        self.node_colors = {
            '1': 'blue',
            '2': 'red',
            '3': 'green',
            '4': 'purple',
            '5': 'orange'
        }

        # Inicializar el bot de Telegram
        self.telegram_token = '7286163016:AAHkq44HCgiEH-rNTsFp-MDUHdfh4NmrAJI'
        self.telegram_chat_id = '-1002178641456'
        self.bot = Bot(token=self.telegram_token)

        # Cargar variables de entorno para Twitter
        load_dotenv()
        TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
        TWITTER_API_SECRET_KEY = os.getenv('TWITTER_API_SECRET_KEY')
        TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
        TWITTER_ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

        # Autenticación con Twitter
        auth = tweepy.OAuth1UserHandler(
            TWITTER_API_KEY,
            TWITTER_API_SECRET_KEY,
            TWITTER_ACCESS_TOKEN,
            TWITTER_ACCESS_TOKEN_SECRET
        )
        self.twitter_api = tweepy.API(auth)

    def setup_gui(self):
        # Estilo personalizado para botones
        self.style.configure('TButton', font=self.normal_font, padding=6)
        self.style.configure('TLabel', font=self.normal_font)
        self.style.configure('Treeview.Heading', font=self.normal_font, background='#3E4149', foreground='white')
        self.style.configure('Treeview', font=self.normal_font)

        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Título
        title_label = ttk.Label(main_frame, text="Gestor de Nodos LoRa", font=self.title_font)
        title_label.pack(pady=10)

        # Frame para selección de puerto y configuración
        port_config_frame = ttk.Frame(main_frame)
        port_config_frame.pack(fill=tk.X, pady=5)

        self.port_var = tk.StringVar()
        ttk.Label(port_config_frame, text="Puerto:", font=self.normal_font).pack(side=tk.LEFT, padx=5)
        self.port_combo = ttk.Combobox(port_config_frame, textvariable=self.port_var, state="readonly", width=15)
        self.port_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(port_config_frame, text="Conectar", command=self.connect_serial).pack(side=tk.LEFT, padx=5)
        ttk.Button(port_config_frame, text="Actualizar Puertos", command=self.update_available_ports).pack(side=tk.LEFT, padx=5)

        # Separador
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Frame para agregar nodos
        add_node_frame = ttk.Frame(main_frame)
        add_node_frame.pack(fill=tk.X, pady=5)

        self.node_id_var = tk.StringVar()
        ttk.Label(add_node_frame, text="ID del Nodo:", font=self.normal_font).pack(side=tk.LEFT, padx=5)
        ttk.Entry(add_node_frame, textvariable=self.node_id_var, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(add_node_frame, text="Agregar Nodo", command=self.add_node).pack(side=tk.LEFT, padx=5)

        # Frame para la lista, mensajes y gráfica
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Frame para la lista de nodos
        list_frame = ttk.Frame(content_frame)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        ttk.Label(list_frame, text="Nodos en el Sistema:", font=self.normal_font).pack(anchor=tk.W)

        # Crear Treeview para mostrar nodos
        self.tree = ttk.Treeview(list_frame, columns=('ID', 'Estado'), show='headings', height=15)
        self.tree.heading('ID', text='ID del Nodo')
        self.tree.heading('Estado', text='Estado')
        self.tree.column('ID', width=100, anchor=tk.CENTER)
        self.tree.column('Estado', width=100, anchor=tk.CENTER)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Scrollbar para el Treeview
        tree_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Asociar evento de doble clic al Treeview
        self.tree.bind('<Double-1>', self.on_treeview_double_click)

        # Frame para mostrar mensajes seriales y gráfica
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        # Frame para mostrar mensajes seriales
        serial_frame = ttk.Frame(right_frame)
        serial_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(serial_frame, text="Comunicación Serial:", font=self.normal_font).pack(anchor=tk.W)

        # Text widget para mostrar mensajes
        self.serial_text = tk.Text(serial_frame, height=10, wrap=tk.NONE, font=self.normal_font)
        self.serial_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Scrollbars para el Text widget
        text_scrollbar_y = ttk.Scrollbar(serial_frame, orient=tk.VERTICAL, command=self.serial_text.yview)
        self.serial_text.configure(yscrollcommand=text_scrollbar_y.set)
        text_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        text_scrollbar_x = ttk.Scrollbar(serial_frame, orient=tk.HORIZONTAL, command=self.serial_text.xview)
        self.serial_text.configure(xscrollcommand=text_scrollbar_x.set)
        text_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        # Frame para la gráfica
        graph_frame = ttk.Frame(right_frame)
        graph_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(graph_frame, text="Datos del Sensor:", font=self.normal_font).pack(anchor=tk.W)

        # Crear la figura de matplotlib
        self.fig, self.ax = plt.subplots()
        self.ax.set_xlabel('Tiempo (s)')
        self.ax.set_ylabel('Valor del Sensor')
        self.ax.set_title('Gráfica en Tiempo Real')
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Frame para controles
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=5)

        # Eliminar o comentar el botón de activación si no se necesita
        # ttk.Button(control_frame, text="Activar Nodo Seleccionado", command=self.activate_selected_node).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Actualizar Lista", command=self.update_node_list).pack(side=tk.LEFT, padx=5)

    def on_treeview_double_click(self, event):
        # Obtener el item en la posición del doble clic
        item = self.tree.identify_row(event.y)
        if item:
            node_id = self.tree.item(item, 'values')[0]
            self.send_activation_command(node_id)

    def update_available_ports(self):
        # Obtener lista de puertos disponibles
        ports = [port.device for port in serial.tools.list_ports.comports()]

        if not ports:
            messagebox.showinfo("Puertos", "No se encontraron puertos seriales")
            self.port_combo['values'] = []
        else:
            self.port_combo['values'] = ports
            self.port_combo.set(ports[0])  # Seleccionar primer puerto por defecto

    def connect_serial(self):
        selected_port = self.port_var.get()

        if not selected_port:
            messagebox.showerror("Error", "Seleccione un puerto serial")
            return

        # Cerrar puerto anterior si está abierto
        if self.serial_port and self.serial_port.is_open:
            self.cleanup()

        try:
            self.serial_port = serial.Serial(
                port=selected_port,
                baudrate=115200,
                timeout=1
            )
            messagebox.showinfo("Conexión", f"Conectado al puerto {selected_port}")

            # Iniciar monitoreo serial
            self.start_serial_monitoring()
        except serial.SerialException as e:
            messagebox.showerror("Error", f"No se pudo abrir el puerto {selected_port}: {e}")

    def add_node(self):
        node_id = self.node_id_var.get().strip()
        if not node_id:
            messagebox.showwarning("Advertencia", "Por favor, ingrese un ID de nodo válido")
            return

        if node_id in self.nodes:
            messagebox.showwarning("Advertencia", "Este ID de nodo ya existe")
            return

        self.nodes[node_id] = False  # Inicialmente inactivo

        # Inicializar listas de datos para este nodo
        self.sensor_data[node_id] = []
        self.time_data[node_id] = []
        
        # Asignar color del nodo
        color = self.node_colors.get(node_id, 'gray')
        self.lines[node_id], = self.ax.plot([], [], 
                                           label=f'Nodo {node_id}',
                                           color=color)

        self.update_node_list()
        self.node_id_var.set("")  # Limpiar entrada
        self.ax.legend()  # Actualizar leyenda
        self.canvas.draw()

    def activate_selected_node(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Advertencia", "Por favor, seleccione un nodo para activar")
            return

        node_id = self.tree.item(selection[0])['values'][0]
        self.send_activation_command(node_id)

    def send_activation_command(self, node_id: str):
        if self.serial_port and self.serial_port.is_open:
            try:
                command = f"A{node_id}"
                self.serial_port.write(command.encode())
                messagebox.showinfo("Info", f"Comando de activación enviado para nodo {node_id}")
                # Mostrar comando enviado en la pantalla de comunicación serial
                self.append_serial_message(f"Enviado: {command.strip()}")
            except serial.SerialException as e:
                messagebox.showerror("Error", f"Error al enviar comando: {e}")
        else:
            messagebox.showerror("Error", "Puerto serial no disponible")

    def update_node_list(self):
        # Limpiar lista actual
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Actualizar con datos actuales
        for node_id, is_active in self.nodes.items():
            estado = "Activo" if is_active else "Inactivo"
            self.tree.insert('', tk.END, values=(node_id, estado))

    def start_serial_monitoring(self):
        if not self.is_monitoring and self.serial_port:
            self.is_monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor_serial, daemon=True)
            self.monitor_thread.start()

    def monitor_serial(self):
        while self.is_monitoring and self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting:
                    raw_data = self.serial_port.readline()
                    mensaje = raw_data.decode('utf-8').strip()
                    if mensaje:
                        self.append_serial_message(f"Recibido: {mensaje}")
                        self.process_serial_message(mensaje)
            except serial.SerialException as e:
                print(f"Error en monitoreo serial: {e}")
                break
            time.sleep(0.1)

    def append_serial_message(self, message: str):
        self.serial_text.insert(tk.END, message + '\n')
        self.serial_text.see(tk.END)  # Hacer scroll hasta el final

    async def send_telegram_message(self, message):
        """Función asíncrona para enviar mensajes por Telegram"""
        await self.bot.send_message(chat_id=self.telegram_chat_id, text=message)

    def send_telegram_sync(self, message):
        """Función auxiliar para enviar mensajes desde código síncrono"""
        asyncio.run(self.send_telegram_message(message))

    def process_serial_message(self, mensaje: str):
        if mensaje.startswith('N'):
            try:
                content = mensaje[1:].strip()
                node_part, sensor_value_part = content.split(':')
                node_id = node_part.strip()
                sensor_value = float(sensor_value_part.strip())
                
                print(f"Procesando mensaje del nodo {node_id}")  # Debug

                # Verificar si es un nuevo nodo
                if node_id not in self.sensor_data:
                    print(f"Nuevo nodo detectado: {node_id}")
                    self.sensor_data[node_id] = []
                    self.time_data[node_id] = []
                    color = self.node_colors.get(node_id, 'gray')
                    self.lines[node_id], = self.ax.plot([], [], 
                                                      label=f'Nodo {node_id}',
                                                      color=color,
                                                      linewidth=2)
                    self.ax.legend()

                # **Actualizar el estado del nodo a activo**
                self.nodes[node_id] = True
                self.root.after(0, self.update_node_list)

                # Agregar nuevos datos con tiempo relativo
                current_time = time.time()
                if not self.time_data[node_id]:  # Primer dato
                    self.time_data[node_id].append(0)
                    self.start_time = current_time
                else:
                    elapsed_time = current_time - self.start_time
                    self.time_data[node_id].append(elapsed_time)
                
                self.sensor_data[node_id].append(sensor_value)

                # Mantener solo los últimos 100 puntos
                window_size = 100
                if len(self.sensor_data[node_id]) > window_size:
                    self.sensor_data[node_id] = self.sensor_data[node_id][-window_size:]
                    self.time_data[node_id] = self.time_data[node_id][-window_size:]

                self.update_plot()

            except ValueError as e:
                print(f"Error procesando mensaje de sensor: {e}")

        elif mensaje.startswith('DN'):
            try:
                # Obtener el ID del nodo
                node_id = mensaje[3].strip()  # Asegúrate de que es el índice correcto
                print(f"Procesando mensaje de desactivación del nodo {node_id}")

                # Enviar mensaje por Telegram de forma sincronizada
                self.send_telegram_sync(f"Se estima que la carretera cubierta con el nodo {node_id} presenta fallos.")

                # Verificar si existen suficientes datos para calcular el promedio
                if node_id in self.sensor_data and len(self.sensor_data[node_id]) >= 5:
                    last_readings = self.sensor_data[node_id][-5:]  # Obtener últimos 5 datos
                    average_value = sum(last_readings) / len(last_readings)

                    # Preparar los datos para Firebase
                    data = {
                        'node_id': node_id,
                        'average_sensor_value': average_value,
                        'timestamp': firestore.SERVER_TIMESTAMP
                    }

                    # Guardar datos en Firebase
                    try:
                        db.collection('sensor_data').add(data)
                        print(f"Datos del nodo {node_id} enviados a Firebase.")
                    except Exception as e:
                        print(f"Error al guardar en Firebase: {e}")
                else:
                    print(f"No hay suficientes datos para el nodo {node_id}.")

                # Enviar tweet con el promedio
                if node_id in self.sensor_data and len(self.sensor_data[node_id]) >= 5:
                    tweet_message = f"Nodo {node_id} desactivado. Promedio de sensor de los últimos 5 datos: {average_value:.2f}"
                    self.send_twitter_message(tweet_message)

                # Opcional: Desactivar el nodo en la interfaz
                self.nodes[node_id] = False
                self.root.after(0, self.update_node_list)

                # Opcional: Limpiar datos del nodo
                # self.sensor_data[node_id] = []
                # self.time_data[node_id] = []

            except Exception as e:
                print(f"Error procesando mensaje de desactivación: {e}")

    def update_plot(self):
        self.ax.clear()
        
        for node_id in self.sensor_data:
            if self.time_data[node_id] and self.sensor_data[node_id]:
                color = self.node_colors.get(node_id, 'gray')
                self.lines[node_id], = self.ax.plot(self.time_data[node_id], 
                                                  self.sensor_data[node_id],
                                                  label=f'Nodo {node_id}',
                                                  color=color,
                                                  linewidth=2)

        self.ax.set_xlabel('Tiempo (s)')
        self.ax.set_ylabel('Valor del Sensor')
        self.ax.set_title('Gráfica en Tiempo Real')
        self.ax.grid(True)
        
        if any(self.sensor_data.values()):
            all_times = [t for times in self.time_data.values() for t in times]
            all_values = [v for values in self.sensor_data.values() for v in values]
            
            if all_times and all_values:
                xmin = max(0, max(all_times) - 30)  # Mostrar últimos 30 segundos
                xmax = max(all_times) + 1
                self.ax.set_xlim(xmin, xmax)
                
                ymin = min(all_values)
                ymax = max(all_values)
                
                if ymin == ymax:
                    # Ajustar ligeramente los límites para evitar valores idénticos
                    ymin -= 1
                    ymax += 1

                margin = (ymax - ymin) * 0.1
                self.ax.set_ylim(ymin - margin, ymax + margin)

        self.ax.legend()
        self.canvas.draw()

    def cleanup(self):
        self.is_monitoring = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()

    def send_twitter_message(self, message: str):
        try:
            self.twitter_api.update_status(status=message)
            print(f"Tweet enviado: {message}")
        except Exception as e:
            print(f"Error al enviar tweet: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = LoRaNodeManager(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.cleanup(), root.destroy()))
    root.mainloop()