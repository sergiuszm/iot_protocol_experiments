import logging
import asyncio
from time import sleep
import argparse

from aiocoap import *

logging.basicConfig(level=logging.DEBUG)

SERVER_IP = '129.242.17.213'
SERVER_PORT = 31416

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

async def do_request(r_type, url, m_type):
    if r_type == 'GET':
        request = Message(code=GET, mtype=NON if m_type == 'NON' else CON, uri=f'coap://{SERVER_IP}:{SERVER_PORT}/{url}')
        request.opt.block2 = (0, 0, 4)
    else:
        request = Message(code=POST, mtype=NON if m_type == 'NON' else CON, uri=f'coap://{SERVER_IP}:{SERVER_PORT}/{url}', payload=MSG_TYPE[url])

    protocol = await Context.create_client_context()

    try:
        response = await protocol.request(request).response
    except Exception as e:
        print('Failed to fetch resource:')
        print(e)
    else:
        print('Result: %s\n%r'%(response.code, response.payload))
        print('Response len: %d'%(len(response.payload)))
        print('-----------------------------------------')
        sleep(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MQTT publisher')
    parser.add_argument('request_type', type=str, choices=['GET', 'POST'])
    parser.add_argument('url', type=str, choices=['short', 'middle', 'long'])
    parser.add_argument('msg_type', type=str, choices=['NON', 'CON'])
    args = parser.parse_args()

    asyncio.get_event_loop().run_until_complete(do_request(args.request_type, args.url, args.msg_type))
