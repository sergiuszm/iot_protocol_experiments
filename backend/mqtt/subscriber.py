import paho.mqtt.client as paho
import datetime
import argparse

def get_time():
    time_object = datetime.datetime.now()
    timestamp = time_object.strftime("%Y-%m-%d %H:%M:%S")
    date = time_object.strftime("%Y-%m-%d")
    return timestamp, date

def on_message(mosq, obj, msg):
    timestamp, date = get_time()
    print("%s: %-20s qos: %d, payload_bytes: %dB, payload: %s" % (timestamp, msg.topic, msg.qos, len(msg.payload), msg.payload))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='MQTT publisher')
    parser.add_argument('qos', type=int, choices=[0, 1, 2])
    args = parser.parse_args()

    client = paho.Client()
    client.enable_logger(logger=None)
    client.username_pw_set('user_name', 'password')
    client.on_message = on_message

    client.connect("lmi034-1.cs.uit.no", 31417, 60)

    client.subscribe([("/short", args.qos), ("/middle", args.qos), ("/long", args.qos)])

    while client.loop() == 0:
        pass
