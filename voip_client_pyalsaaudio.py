import socket
import alsaaudio
import threading
import paho.mqtt.client as mqtt
import time
import json

# Configuration
FORMAT = alsaaudio.PCM_FORMAT_S16_LE
CHANNELS = 1
RATE = 44100  # Ensure this is a supported sample rate
CHUNK = 1024
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
DRONE_ID = "drone101"
MQTT_TOPIC_CALL = f"{DRONE_ID}/call"
MQTT_TOPIC_DATA = f"{DRONE_ID}/data"
VOIP_SERVER = '3.208.18.29'
JSON_FILE = 'device.json'
DEVICE_INDEX = 1  # Replace with your USB audio device index

# Global variables
client_socket = None
receive_thread = None
send_thread = None
connected_to_server = False
stop_event = threading.Event()

def on_message(client, userdata, message):
    global connected_to_server
    msg = message.payload.decode()
    print(f"Received message: {msg} on topic: {message.topic}")
    if msg == "on" and not connected_to_server:
        connected_to_server = True
        start_client()
    elif msg == "off" and connected_to_server:
        connected_to_server = False
        stop_client()

def start_client(server_host=VOIP_SERVER, server_port=50007):
    global client_socket, receive_thread, send_thread, stop_event

    stop_event.clear()
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((server_host, server_port))
    print("Connected to server")

    input_device = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL, cardindex=DEVICE_INDEX)
    output_device = alsaaudio.PCM(alsaaudio.PCM_PLAYBACK, alsaaudio.PCM_NORMAL, cardindex=DEVICE_INDEX)

    input_device.setchannels(CHANNELS)
    input_device.setrate(RATE)
    input_device.setformat(FORMAT)
    input_device.setperiodsize(CHUNK)

    output_device.setchannels(CHANNELS)
    output_device.setrate(RATE)
    output_device.setformat(FORMAT)
    output_device.setperiodsize(CHUNK)

    def receive():
        while not stop_event.is_set():
            try:
                data = client_socket.recv(CHUNK)
                if not data:
                    break
                output_device.write(data)
            except (ConnectionResetError, OSError) as e:
                print(f"Error in receive thread: {e}")
                break

    def send():
        while not stop_event.is_set():
            try:
                _, data = input_device.read()
                client_socket.sendall(data)
            except (ConnectionResetError, OSError) as e:
                print(f"Error in send thread: {e}")
                break

    receive_thread = threading.Thread(target=receive)
    send_thread = threading.Thread(target=send)

    receive_thread.start()
    send_thread.start()

def stop_client():
    global client_socket, receive_thread, send_thread, stop_event
    stop_event.set()

    if receive_thread:
        receive_thread.join()
    if send_thread:
        send_thread.join()

    if client_socket:
        client_socket.close()

    print("Disconnected from server")

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with code {rc}")
    client.subscribe(MQTT_TOPIC_CALL)
    client.publish(MQTT_TOPIC_DATA, f"{DRONE_ID} joined system")
    start_periodic_publish()

def start_periodic_publish():
    def publish_data():
        while not stop_event.is_set():
            try:
                with open(JSON_FILE, 'r') as f:
                    data = json.load(f)
                    mqtt_client.publish(MQTT_TOPIC_DATA, json.dumps(data))
                    print(f"Published: {json.dumps(data)}")
            except FileNotFoundError:
                print(f"{JSON_FILE} not found.")
            except json.JSONDecodeError:
                print(f"Error decoding JSON from {JSON_FILE}.")
            time.sleep(60)

    periodic_thread = threading.Thread(target=publish_data)
    periodic_thread.daemon = True
    periodic_thread.start()

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

print("MQTT client started and subscribed to topic. Waiting for messages...")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    stop_client()
    print("MQTT client stopped")
