import machine
import socket
from time import sleep
from comm import TimedStep, WLAN, LTE, NBIOT, NBIOTCoAPSocket, NBIOTTCPSocket, NBIOTMQTTClient, NBIOTUDPSocket, TimeoutError
import microcoapy
import logging
from uping import ping
# from uos import urandom
import ucrypto as crypto
from microcoapy.coap_macros import COAP_OPTION_NUMBER, COAP_TYPE, COAP_METHOD, COAP_CONTENT_FORMAT, CoapResponseCode
from microcoapy.coap_packet import CoapPacket
from mqtt import MQTTClient

# HTTP configuration
SERVER_IP = '129.242.17.213'
HOST = 'lmi034-1.cs.uit.no'
TCP_PORT = 31415
TCP_DUMP = True
TCP_DUMP_DELAY = 20

# CoAP configuration
COAP_SERVER_IP = '129.242.17.213'
COAP_PORT = 31416

# MQTT configuration
MQTT_SERVER_IP = '129.242.17.213'
MQTT_PORT = 31417
MQTT_USER = 'user'
MQTT_PASSWORD = 'password'

# RTT measurements configuration
REPEAT_TIMES = 5

_logger = logging.getLogger("main", logging.INFO)

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

def to_minimum_bytes(value):
    return value.to_bytes((get_bit_length(value) + 7) // 8, 'big')

def get_bit_length(n):
        return len(bin(n)) - 2

class CoAPMessageCallback:
    def __init__(self):
        self.current_packet = None
        self.packets = []
        self.blockwise = False
        self.blockwise_opt = None

    def receivedMessage(self, packet, sender):
        self.current_packet = packet
        self._handle_blockwise()
        payload = packet.payload
        if not self.blockwise:
            payload = bytearray()
            if len(self.packets) > 1:
                for pkt in self.packets:
                    if pkt.payload is not None:
                        payload.extend(pkt.payload)
            else:
                payload = packet.payload
            if payload is not None and len(payload) > 0:
                _logger.info('Total response size: {}'.format(len(payload)))
            # _logger.info(payload)
        
    def _handle_blockwise(self):
        for option in self.current_packet.options:
            if option.number == COAP_OPTION_NUMBER.COAP_BLOCK2 or option.number == COAP_OPTION_NUMBER.COAP_BLOCK1:
                self.packets.append(self.current_packet)
                self.blockwise = True
                as_integer = int.from_bytes(option.buffer, 'big')
                block_number = as_integer >> 4
                more = bool(as_integer & 0x08)
                szx = as_integer & 0x07
                self.blockwise_opt = (block_number, more, szx)
                if not more:
                    self.blockwise = False
                return

        self.blockwise = False

class MQTTMessageCallback:
    def __init__(self):
        self.payload = bytearray()

    def receivedMessage(self, topic, payload):
        self.payload = payload
        _logger.info('Total response size: {}'.format(len(payload)))
        _logger.info(payload)

def send_http_data(url, custom_socket=None):
    _, _, host, path = url.split('/', 3)
    addr = (SERVER_IP, TCP_PORT)
    data = MSG_TYPE[path]
    data_size = len(data)
    response_data = ''

    try:
        data = '--------------------------627c1552744e7f41\r\n'\
            'Content-Disposition: form-data; name="file"; filename="short.txt"\r\n'\
            'Content-Type: text/plain\r\n\r\n'\
            '%s\r\n'\
            '--------------------------627c1552744e7f41--\r\n' % data.decode()

        header = 'POST /%s HTTP/1.0\r\n'\
            'Host: %s\r\nContent-Length: %d\r\n'\
            'Content-Type: multipart/form-data; boundary=------------------------627c1552744e7f41\r\n\r\n'

        header = header % (path, host, len(data))
        request = '{}{}'.format(header, data)

        request = bytes(request, 'utf8')

        with TimedStep('HTTP POST Request: {}'.format(url), logger=_logger):
            if custom_socket is not None:
                s = custom_socket
            else:
                s = socket.socket()

            s.connect(addr)

            send_bytes = s.send(request)
            _logger.info('Total sent size: {}B. Payload size: {}B'.format(send_bytes, data_size))
            r_data = None
            while True:
                r_data = s.recv(1024)
                if r_data:
                    try:
                        response_data += str(r_data, 'utf8')
                    except UnicodeError:
                        _logger.warning('UnicodeError for data:')
                        _logger.warning(r_data)
                else:
                    break

            s.close()
    except TimeoutError:
        s.close()
        _logger.error('HTTP POST Request: {} timed out!'.format(url))
        return

    if response_data.find('R_OK') < 0:
        _logger.error('HTTP POST Request: failed!')
        return
    
    _logger.info('Total response size: {}B. Payload size: {}B'.format(len(response_data), len(response_data.split('\r\n\r\n')[1])))

def get_http_data(url, custom_socket=None):
    _, _, host, path = url.split('/', 3)

    addr = (SERVER_IP, TCP_PORT)
    all_data = ""
    try:
        with TimedStep('HTTP GET Request: {}'.format(url), logger=_logger):
            if custom_socket is not None:
                s = custom_socket
            else:
                s = socket.socket()

            s.connect(addr)
            s.send(bytes('GET /%s HTTP/1.0\r\nHost: %s\r\n\r\n' % (path, host), 'utf8'))
            while True:
                data = s.recv(1024)
                if data:
                    try:
                        all_data += str(data, 'utf8')
                    except UnicodeError:
                        _logger.warning('UnicodeError for data:')
                        _logger.warning(data)
                else:
                    break
            
            s.close()
    except TimeoutError:
        s.close()
        _logger.error('HTTP GET Request: {} timed out!'.format(url))
        return


    _logger.info('Total response size: {}B. Payload size: {}B'.format(len(all_data), len(all_data.split('\r\n\r\n')[1])))

def perform_tcp_handshake(custom_socket=None):
    with TimedStep('TCP time', logger=_logger):
        addr = (SERVER_IP, TCP_PORT)
        if custom_socket is not None:
            s = custom_socket
        else:
            s = socket.socket()
        s.connect(addr)
        s.close()

def get_coap_data(url, coap_type=COAP_TYPE.COAP_CON, custom_socket=None):
    def create_packet(ip, port, url, type, method, token, payload, content_format, query_option):
        packet = CoapPacket()
        packet.type = type
        packet.method = method
        packet.token = token
        packet.payload = payload
        packet.content_format = content_format
        packet.query = query_option

        randBytes = crypto.getrandbits(32)
        packet.messageid = (randBytes[0] << 8) | randBytes[1]
        packet.setUriHost(ip)
        packet.setUriPath(url)

        return packet

    _, _, host, path = url.split('/', 3)

    token = crypto.getrandbits(32)
    client = microcoapy.Coap()
    client_pool = 2000
    response = CoAPMessageCallback()
    client.resposeCallback = response.receivedMessage
    if custom_socket is not None:
        client.setCustomSocket(custom_socket)
    else:
        client.start()

    with TimedStep('CoAP GET {} Request: {}'.format('NON' if coap_type == COAP_TYPE.COAP_NONCON else 'CON', url), logger=_logger):
        packet = create_packet(host, COAP_PORT, path, coap_type, COAP_METHOD.COAP_GET, token, None, COAP_CONTENT_FORMAT.COAP_NONE, None)
        if custom_socket is not None:
            if custom_socket.__class__.__name__ == NBIOTUDPSocket.__name__:
                # requests block size 256B (szx=4) instead of the default 1024B (szx=6)
                # @see: https://tools.ietf.org/html/rfc7959#section-4
                block2_payload = 4
            elif custom_socket.__class__.__name__ == NBIOTCoAPSocket.__name__:
                # requests block size 512B (szx=5) instead of the default 1024B (szx=6)
                # @see: https://tools.ietf.org/html/rfc7959#section-4
                block2_payload = 5
            else:
                raise RuntimeError('Unsupported socket!')

            client_pool = 10000
            block2_payload = to_minimum_bytes(block2_payload)
            packet.addOption(COAP_OPTION_NUMBER.COAP_BLOCK2, block2_payload)
        
        client.state = client.TRANSMISSION_STATE.STATE_IDLE
        client.sendPacket(host, COAP_PORT, packet)

        status = client.poll(client_pool)
        if not status:
            client.stop()
            raise TimeoutError('Expected response did not arrive!')

        while response.blockwise:
            if client.packet is None:
                raise TimeoutError('Sent packet status unknown!')
            last_packet = client.packet
            packet = CoapPacket()
            packet.type = last_packet.type
            packet.method = last_packet.method
            old_token = int.from_bytes(last_packet.token, 'big')
            packet.token = (old_token + 1) % (2 ** 16)
            packet.token = to_minimum_bytes(packet.token)
            packet.payload = last_packet.payload
            packet.content_format = last_packet.content_format
            packet.query = last_packet.query

            client.state = client.TRANSMISSION_STATE.STATE_IDLE
            packet.messageid = 0xFFFF & (1 + last_packet.messageid)
            packet.setUriHost(host)
            packet.setUriPath(path)
            block2_payload = ((response.blockwise_opt[0] + 1) << 4) + (False * 0x08) + response.blockwise_opt[2]
            block2_payload = to_minimum_bytes(block2_payload)
            packet.addOption(COAP_OPTION_NUMBER.COAP_BLOCK2, block2_payload)
            status = client.sendPacket(host, COAP_PORT, packet)
            if not status:
                client.stop()
                raise TimeoutError('Expected response did not arrive!')

            client.poll(client_pool)

    client.stop()

def send_coap_data(url, coap_type=COAP_TYPE.COAP_CON, custom_socket=None):
    ACK_TIMEOUT = 2
    ACK_RANDOM_FACTOR = 1.5
    MAX_RETRANSMIT = 4

    def create_packet(ip, port, url, type, method, token, payload, content_format, query_option):
        packet = CoapPacket()
        packet.type = type
        packet.method = method
        packet.token = token
        packet.payload = payload
        packet.content_format = content_format
        packet.query = query_option

        randBytes = crypto.getrandbits(32)
        packet.messageid = (randBytes[0] << 8) | randBytes[1]
        packet.setUriHost(ip)
        packet.setUriPath(url)

        return packet

    _, _, host, path = url.split('/', 3)

    token = crypto.getrandbits(32)
    client = microcoapy.Coap()
    response = CoAPMessageCallback()
    client.resposeCallback = response.receivedMessage
    if custom_socket is not None:
        if custom_socket.__class__.__name__ == NBIOTCoAPSocket.__name__:
            raise RuntimeError('Unsupported socket!')
        client.setCustomSocket(custom_socket)
    else:
        client.start()

    payload = MSG_TYPE[path]
    payload_parts = [payload]
    client_pool = 2000
    if not custom_socket and len(payload) > 1024:
        payload_parts = [payload[i:i+1024] for i in range(0, len(payload), 1024)]
    elif custom_socket is not None and len(payload) > 256:
        payload_parts = [payload[i:i+256] for i in range(0, len(payload), 256)]
        client_pool = 5000

    payload_parts_len = len(payload_parts)
    payload_parts.reverse()
    with TimedStep('CoAP POST {} Request: {}'.format('NON' if coap_type == COAP_TYPE.COAP_NONCON else 'CON', url), logger=_logger):
        payload = payload_parts.pop()
        packet = create_packet(host, COAP_PORT, path, coap_type, COAP_METHOD.COAP_POST, token, payload, COAP_CONTENT_FORMAT.COAP_NONE, None)
        more = False if len(payload_parts) == 0 else True
        if custom_socket is not None and payload_parts_len > 1:
            # requests block size 256B (szx=4) instead of the default 1024B (szx=6)
            # @see: https://tools.ietf.org/html/rfc7959#section-4
            block1_payload = 0 + (more * 0x08) + 4
        else:
            block1_payload = 0 + (more * 0x08) + 6
        
        block1_payload = to_minimum_bytes(block1_payload)
        packet.addOption(COAP_OPTION_NUMBER.COAP_BLOCK1, block1_payload)

        client.state = client.TRANSMISSION_STATE.STATE_IDLE
        client.sendPacket(host, COAP_PORT, packet)

        status = client.poll(client_pool)
        if not status:
            client.stop()
            raise TimeoutError('Expected response did not arrive!')

        while response.blockwise:
            last_packet = client.packet
            packet = CoapPacket()
            packet.type = last_packet.type
            packet.method = last_packet.method
            old_token = int.from_bytes(last_packet.token, 'big')
            packet.token = (old_token + 1) % (2 ** 16)
            packet.token = to_minimum_bytes(packet.token)
            packet.payload = payload_parts.pop()
            packet.content_format = last_packet.content_format
            packet.query = last_packet.query

            client.state = client.TRANSMISSION_STATE.STATE_IDLE
            packet.messageid = 0xFFFF & (1 + last_packet.messageid)
            packet.setUriHost(host)
            packet.setUriPath(path)
            more = False if len(payload_parts) == 0 else True
            block1_payload = ((response.blockwise_opt[0] + 1) << 4) + (more * 0x08) + response.blockwise_opt[2]
            block1_payload = to_minimum_bytes(block1_payload)
            packet.addOption(COAP_OPTION_NUMBER.COAP_BLOCK1, block1_payload)
            client.sendPacket(host, COAP_PORT, packet)
            status = client.poll(client_pool)

        if status:
            last_packet = response.packets.pop()
            class_, detail = CoapResponseCode.decode(last_packet.method)
            code = '{}.{:02d}'.format(class_, detail)

            # 2.01 = CREATED
            if code == '2.01' and coap_type == COAP_TYPE.COAP_CON:
                packet = CoapPacket()
                packet.type = COAP_TYPE.COAP_ACK
                packet.method = COAP_METHOD.COAP_EMPTY_MESSAGE
                packet.token = last_packet.token
                packet.payload = None
                packet.content_format = COAP_CONTENT_FORMAT.COAP_NONE
                packet.query = None

                client.state = client.TRANSMISSION_STATE.STATE_IDLE
                packet.messageid = last_packet.messageid
                packet.setUriHost(host)
                packet.setUriPath(path)
                if custom_socket is not None: custom_socket.timeout = 0.5
                client.sendPacket(host, COAP_PORT, packet)
                client.poll(20)
        else:
            client.stop()
            raise TimeoutError('Expected response did not arrive!')

    client.stop()

def get_mqtt_data(client, topic, qos=0):
    response = MQTTMessageCallback()
    client.set_callback(response.receivedMessage)

    with TimedStep('MQTT Subscription: {}, qos: {}'.format(topic, qos), logger=_logger):
        client.connect()
        client.subscribe(topic=topic, qos=qos)
        _logger.info('MQTT waiting for msg...')
        client.wait_msg()

        # while True:
        #     client.check_msg()
        if len(response.payload) > 0:
            _logger.info('Received subscribbed msg!')
                # break

        client.disconnect()

def send_mqtt_data(client, topic, payload, qos=0):

    with TimedStep('MQTT Publish: {}, qos: {}'.format(topic, qos), logger=_logger):
        client.connect()
        client.publish(topic=topic, msg=payload, qos=qos)
        client.disconnect()

    sleep(1)

def delay_helper(seconds=TCP_DUMP_DELAY):
    for x in range(0, seconds):
        if seconds - 1 - x == 0:
            print('{}'.format(seconds - x))
        else:
            print('{}'.format(seconds - x), end =' ')
        sleep(1)
        
def repeat_until_succesfull(f, delay=1, with_helper=False):
    while True:
        try:
            f()
            break
        except TimeoutError:
            if with_helper:
                delay_helper(delay)
            else:
                sleep(delay)
            continue

if __name__ == "__main__":
    try:
        radios = [WLAN(), LTE(), NBIOT()]
        for radio in radios:
            with TimedStep('Experiments with {}'.format(radio.type), logger=_logger):
                _logger.info('#### {} START ####'.format(radio.type))
                radio.connect()
                t_socket = None
                cs_socket = None
                cg_socket = None

                if radio.type == 'RADIO_NBIOT':
                    t_socket = NBIOTTCPSocket(radio)
                    cg_socket = NBIOTCoAPSocket(radio, COAP_SERVER_IP, COAP_PORT, reusable=True)
                    cs_socket = NBIOTUDPSocket(radio)
                    m_client = NBIOTMQTTClient(radio, 'fipyra', MQTT_SERVER_IP, MQTT_PORT, MQTT_USER, MQTT_PASSWORD)
                else:
                    m_client = MQTTClient('fipyra', MQTT_SERVER_IP, MQTT_PORT, MQTT_USER, MQTT_PASSWORD)

                if radio.type == 'RADIO_NBIOT':
                    radio.ping(HOST)
                else:
                    ping(HOST)
                    
                if TCP_DUMP:
                    _logger.info('TCP DUMP start: TCP handshare')
                    delay_helper()
                    perform_tcp_handshake(t_socket)
                    _logger.info('TCP DUMP end: TCP handshare')

                    for path in ['short', 'middle', 'long']:
                        _logger.info('HTTP GET DUMP start: {}'.format(path))
                        delay_helper()
                        get_http_data('http://{}/{}'.format(HOST, path), t_socket)
                        _logger.info('HTTP GET DUMP end: {}'.format(path))

                    for path in ['short', 'middle', 'long']:
                        _logger.info('HTTP POST DUMP start: {}'.format(path))
                        delay_helper()
                        send_http_data('http://{}/{}'.format(HOST, path), t_socket)
                        _logger.info('HTTP POST DUMP end: {}'.format(path))

                    for path in ['short', 'middle', 'long']:
                        _logger.info('CoAP GET NON DUMP start: {}'.format(path))
                        delay_helper()
                        repeat_until_succesfull(lambda: get_coap_data('coap://{}/{}'.format(COAP_SERVER_IP, path), COAP_TYPE.COAP_NONCON, cg_socket), TCP_DUMP_DELAY, True)
                        _logger.info('CoAP GET NON DUMP end: {}'.format(path))

                    for path in ['short', 'middle', 'long']:
                        _logger.info('CoAP GET CON DUMP start: {}'.format(path))
                        delay_helper()
                        repeat_until_succesfull(lambda: get_coap_data('coap://{}/{}'.format(COAP_SERVER_IP, path), COAP_TYPE.COAP_CON, cg_socket), TCP_DUMP_DELAY, True)
                        _logger.info('CoAP GET CON DUMP end: {}'.format(path))

                    if radio.type == 'RADIO_NBIOT':
                        for path in ['short', 'middle', 'long']:
                            _logger.info('CoAP GET NON DUMP start (NBIOTUDPSocket): {}'.format(path))
                            delay_helper()
                            repeat_until_succesfull(lambda: get_coap_data('coap://{}/{}'.format(COAP_SERVER_IP, path), COAP_TYPE.COAP_NONCON, cs_socket), TCP_DUMP_DELAY, True)
                            _logger.info('CoAP GET NON DUMP end (NBIOTUDPSocket): {}'.format(path))

                        for path in ['short', 'middle', 'long']:
                            _logger.info('CoAP GET CON DUMP start (NBIOTUDPSocket): {}'.format(path))
                            delay_helper()
                            repeat_until_succesfull(lambda: get_coap_data('coap://{}/{}'.format(COAP_SERVER_IP, path), COAP_TYPE.COAP_CON, cs_socket), TCP_DUMP_DELAY, True)
                            _logger.info('CoAP GET CON DUMP end (NBIOTUDPSocket): {}'.format(path))

                    for path in ['short', 'middle', 'long']:
                        _logger.info('CoAP POST NON DUMP start: {}'.format(path))
                        delay_helper()
                        repeat_until_succesfull(lambda: send_coap_data('coap://{}/{}'.format(COAP_SERVER_IP, path), COAP_TYPE.COAP_NONCON, cs_socket), TCP_DUMP_DELAY, True)
                        _logger.info('CoAP POST NON DUMP end: {}'.format(path))

                    for path in ['short', 'middle', 'long']:
                        _logger.info('CoAP POST CON DUMP start: {}'.format(path))
                        delay_helper()
                        repeat_until_succesfull(lambda: send_coap_data('coap://{}/{}'.format(COAP_SERVER_IP, path), COAP_TYPE.COAP_CON, cs_socket), TCP_DUMP_DELAY, True)
                        _logger.info('CoAP POST CON DUMP end: {}'.format(path))

                    for topic in ['short', 'middle', 'long']:
                        if topic == 'long' and radio.type == 'RADIO_NBIOT':
                            continue
                        _logger.info('MQTT publish qos-0 DUMP start: {}'.format(topic))
                        delay_helper()
                        send_mqtt_data(m_client, '/{}'.format(topic), MSG_TYPE[topic])
                        _logger.info('MQTT publish qos-0 DUMP end: {}'.format(topic))

                    for topic in ['short', 'middle', 'long']:
                        if topic == 'long' and radio.type == 'RADIO_NBIOT':
                            continue
                        _logger.info('MQTT publish qos-1 DUMP start: {}'.format(topic))
                        delay_helper()
                        send_mqtt_data(m_client, '/{}'.format(topic), MSG_TYPE[topic], qos=1)
                        _logger.info('MQTT publish qos-1 DUMP end: {}'.format(topic))

                _logger.info('TCP HANDSHAKE START')
                for x in range(0, REPEAT_TIMES):
                    perform_tcp_handshake(t_socket)
                    sleep(1)
                _logger.info('TCP HANDSHAKE END')

                # HTTP RTT
                for path in ['short', 'middle', 'long']:
                    _logger.info('HTTP GET START: {}'.format(path))
                    for x in range(0, REPEAT_TIMES):
                        get_http_data('http://{}/{}'.format(HOST, path), t_socket)
                        sleep(1)
                    _logger.info('HTTP GET END: {}'.format(path))

                    _logger.info('HTTP POST START: {}'.format(path))
                    for x in range(0, REPEAT_TIMES):
                        send_http_data('http://{}/{}'.format(HOST, path), t_socket)
                        sleep(1)
                    _logger.info('HTTP POST END: {}'.format(path))

                # CoAP NON RTT
                for path in ['short', 'middle', 'long']:
                    _logger.info('CoAP GET NON START: {}'.format(path))
                    for x in range(0, REPEAT_TIMES):
                        repeat_until_succesfull(lambda: get_coap_data('coap://{}/{}'.format(COAP_SERVER_IP, path), COAP_TYPE.COAP_NONCON, cg_socket))
                        sleep(1)
                    _logger.info('CoAP GET NON END: {}'.format(path))

                    if radio.type == 'RADIO_NBIOT':
                        _logger.info('CoAP GET NON (NBIOTUDPSocket) START: {}'.format(path))
                        for x in range(0, REPEAT_TIMES):
                            repeat_until_succesfull(lambda: get_coap_data('coap://{}/{}'.format(COAP_SERVER_IP, path), COAP_TYPE.COAP_NONCON, cs_socket))
                            sleep(1)
                        _logger.info('CoAP GET NON (NBIOTUDPSocket) END: {}'.format(path))

                    _logger.info('CoAP POST NON START: {}'.format(path))
                    for x in range(0, REPEAT_TIMES):
                        repeat_until_succesfull(lambda: send_coap_data('coap://{}/{}'.format(COAP_SERVER_IP, path), COAP_TYPE.COAP_NONCON, cs_socket))
                        sleep(1)
                    _logger.info('CoAP POST NON END: {}'.format(path))

                # CoAP CON RTT
                for path in ['short', 'middle', 'long']:
                    _logger.info('CoAP GET CON START: {}'.format(path))
                    for x in range(0, REPEAT_TIMES):
                        repeat_until_succesfull(lambda: get_coap_data('coap://{}/{}'.format(COAP_SERVER_IP, path), COAP_TYPE.COAP_CON, cg_socket))
                        sleep(1)
                    _logger.info('CoAP GET CON END: {}'.format(path))

                    if radio.type == 'RADIO_NBIOT':
                        _logger.info('CoAP GET CON (NBIOTUDPSocket) START: {}'.format(path))
                        for x in range(0, REPEAT_TIMES):
                            repeat_until_succesfull(lambda: get_coap_data('coap://{}/{}'.format(COAP_SERVER_IP, path), COAP_TYPE.COAP_CON, cs_socket))
                            sleep(1)
                        _logger.info('CoAP GET CON (NBIOTUDPSocket) END: {}'.format(path))

                    _logger.info('CoAP POST CON START: {}'.format(path))
                    for x in range(0, REPEAT_TIMES):
                        repeat_until_succesfull(lambda: send_coap_data('coap://{}/{}'.format(COAP_SERVER_IP, path), COAP_TYPE.COAP_CON, cs_socket))
                        sleep(1)
                    _logger.info('CoAP POST CON END: {}'.format(path))

                # MQTT qos-0 RTT
                for topic in ['short', 'middle', 'long']:
                    if topic == 'long' and radio.type == 'RADIO_NBIOT':
                        continue
                    
                    _logger.info('MQTT publish qos-0 START: {}'.format(topic))
                    for x in range(0, REPEAT_TIMES):
                        send_mqtt_data(m_client, '/{}'.format(topic), MSG_TYPE[topic])
                        sleep(1)
                    _logger.info('MQTT publish qos-0 END: {}'.format(topic))

                # MQTT qos-1 RTT
                for topic in ['short', 'middle', 'long']:
                    if topic == 'long' and radio.type == 'RADIO_NBIOT':
                        continue
                    
                    _logger.info('MQTT publish qos-1 START: {}'.format(topic))
                    for x in range(0, REPEAT_TIMES):
                        send_mqtt_data(m_client, '/{}'.format(topic), MSG_TYPE[topic], qos=1)
                        sleep(1)
                    _logger.info('MQTT publish qos-1 END: {}'.format(topic))

                if cg_socket is not None:
                    cg_socket.reusable = False
                    cg_socket.close()

                radio.deinit()
                _logger.info('#### {} END ####'.format(radio.type))

    except Exception as e:
        _logger.traceback(e)
