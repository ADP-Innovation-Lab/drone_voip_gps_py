import socket
import pyaudio
import threading
import paho.mqtt.client as mqtt
import time
import json

# Configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
DRONE_ID = "drone101"
MQTT_TOPIC_CALL = f"{DRONE_ID}/call"
MQTT_TOPIC_DATA = f"{DRONE_ID}/data"
VOIP_SERVER = '3.208.18.29'
JSON_FILE = 'device.json'

# Global variables
client_socket = None
audio = None
stream_in = None
stream_out = None
receive_thread = None
send_thread = None
connected_to_server = False
stop_event = threading.Event()

def on_message(client, userdata, message):
    global connected_to_server
    msg = message.payload.decode()
    if msg == "on" and not connected_to_server:
        connected_to_server = True
        start_client()
    elif msg == "off" and connected_to_server:
        connected_to_server = False
        stop_client()

def start_client(server_host=VOIP_SERVER, server_port=50007):
    global client_socket, audio, stream_in, stream_out, receive_thread, send_thread, stop_event

    stop_event.clear()
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((server_host, server_port))
    print("Connected to server")

    audio = pyaudio.PyAudio()
    # Output
    stream_out = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK)

    # Input
    stream_in = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

    def receive():
        while not stop_event.is_set():
            try:
                data = client_socket.recv(CHUNK)
                if not data:
                    break
                stream_out.write(data)
            except (ConnectionResetError, OSError) as e:
                print(f"Error in receive thread: {e}")
                break

    def send():
        while not stop_event.is_set():
            try:
                data = stream_in.read(CHUNK)
                client_socket.sendall(data)
            except (ConnectionResetError, OSError) as e:
                print(f"Error in send thread: {e}")
                break

    receive_thread = threading.Thread(target=receive)
    send_thread = threading.Thread(target=send)

    receive_thread.start()
    send_thread.start()

def stop_client():
    global client_socket, audio, stream_in, stream_out, receive_thread, send_thread, stop_event
    stop_event.set()

    if receive_thread:
        receive_thread.join()
    if send_thread:
        send_thread.join()

    if client_socket:
        client_socket.close()
    if stream_in:
        stream_in.stop_stream()
        stream_in.close()
    if stream_out:
        stream_out.stop_stream()
        stream_out.close()
    if audio:
        audio.terminate()

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
                    lat = data.get('lat', 0.0)
                    lon = data.get('long', 0.0)
                    bat = data.get('bat', "N/A")
                    mqtt_message = f"BAT:{bat} - LAT:{lat} - LONG:{lon}"
                    mqtt_client.publish(MQTT_TOPIC_DATA, mqtt_message)
                    print(f"Published: {mqtt_message}")
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