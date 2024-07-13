import paho.mqtt.client as mqtt

# Define the MQTT broker and topic
mqtt_broker = "cb3ae90baa6241218b1aacfd2a52d6ba.s1.eu.hivemq.cloud"
mqtt_port = 8883
mqtt_topic = "esp32/test"

# Define the MQTT client
client = mqtt.Client("PythonClient")

# Connect to the broker
client.connect(mqtt_broker, mqtt_port)

# Function to publish a message
def publish_message(message):
    client.publish(mqtt_topic, message)
    print(f"Message '{message}' sent to topic '{mqtt_topic}'")

# Publish '1' to turn on the LED
publish_message("1")

# Publish '2' to turn off the LED
# publish_message("2")

# # Disconnect from the broker
# client.disconnect()
