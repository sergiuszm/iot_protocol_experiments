import paho.mqtt.client as paho
import time
import argparse

MSG_TYPE={
    'short': b"It is a simple short response.\n",
    'middle': b"Lorem ipsum dolor sit amet, consectetur adipiscing elit. Integer nisl magna, varius et nunc ut, pharetra posuere ante. "\
            b"Praesent vestibulum tempor vehicula. Nunc vehicula a elit at rhoncus. Proin luctus ex at sapien pretium, a consequat magna maximus. "\
            b"Nunc scelerisque nunc et enim pellentesque, eu porta diam aliquet. Mauris mollis congue justo, ac volutpat nibh consequat sit amet. "\
            b"Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia curae; Curabitur congue nibh ut efficitur est.\n\n",
    'long': b"Lorem ipsum dolor sit amet, consectetur adipiscing elit. Integer quam nulla, tincidunt nec dolor ut, "\
            b"convallis finibus est. Aenean pretium nulla eu dolor ultrices maximus. Phasellus laoreet metus et pellentesque ornare. "\
            b"Praesent ac purus sed quam pulvinar cursus. Suspendisse dictum mollis est non tincidunt. In posuere mauris justo, "\
            b"nec rhoncus tortor vestibulum at. Aenean in lorem augue. Maecenas ante elit, tempor id ante in, pellentesque congue nisl.\n\n"\
            b"Curabitur sit amet pulvinar turpis. Suspendisse potenti. Aenean porta, arcu sed sollicitudin commodo, ante dolor suscipit eros, "\
            b"vitae eleifend velit felis ac risus. Sed vehicula mi sed ultrices ullamcorper. Nulla fringilla ac lacus viverra egestas. "\
            b"Suspendisse metus ligula, ultricies et egestas in, sodales vitae nunc. Quisque aliquam dolor fringilla venenatis aliquam. "\
            b"Praesent tellus diam, luctus eu risus in, scelerisque auctor nunc. Donec odio nibh, venenatis eget condimentum eu, tristique "\
            b"facilisis nunc. Proin arcu ex, congue malesuada consequat a, tempor eu justo. Vivamus sapien magna, venenatis at interdum ut, "\
            b"eleifend eget velit.\n\n"\
            b"Sed a efficitur eros. Vestibulum mattis blandit malesuada. Donec leo quam, facilisis ac tortor eu, fringilla tempus neque. "\
            b"Vestibulum volutpat, diam vel vulputate molestie, nunc velit mollis ipsum, vitae pulvinar urna neque nec leo. Curabitur elit tortor, "\
            b"venenatis sed malesuada at, efficitur quis risus. Fusce ac tellus et ipsum viverra consequat. Proin pretium commodo lacus, "\
            b"quis vestibulum nisl consequat eu. Morbi maximus, neque in tempus finibus, lacus odio tempus magna, sit amet pretium libero.\n\n"
}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='MQTT publisher')
    parser.add_argument('type', type=str, choices=['short', 'middle', 'long'])
    parser.add_argument('qos', type=int, choices=[0, 1, 2])
    args = parser.parse_args()

    client = paho.Client()
    client.username_pw_set('username', 'password')
    client.connect('lmi034-1.cs.uit.no', 31417, 60)

    client.loop_start()
    print('PUBLISHING -->')
    print(MSG_TYPE[args.type])
    infot = client.publish(f'/{args.type}', MSG_TYPE[args.type], qos=args.qos)
    infot.wait_for_publish()
    client.disconnect()
    time.sleep(5)
