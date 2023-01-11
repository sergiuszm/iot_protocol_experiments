import logging
from machine import Timer, Pin
import network
import time
import ubinascii
from machine import UART as serial
import re

_logger = logging.getLogger("comm", logging.INFO)

class TimeoutError(Exception):
    pass

class NBIOTUDPSocketError(Exception):
    pass

class NBIOTCoAPSocketError(Exception):
    pass

class NBIOTHTTPSocketError(Exception):
    pass

class NBIOTTCPSocketError(Exception):
    pass

class MQTTClientError(Exception):
    pass

class TimedStep(object):
    def __init__(self, desc="", logger=None, suppress_exception=False):
        self.desc = desc
        self.logger = logger
        self.suppress_exception = suppress_exception
        self._tschrono = Timer.Chrono()

    def __enter__(self):
        # wdt.feed()
        self._tschrono.start()
        self.logger.info("%s ...", self.desc)

    def __exit__(self, exc_type, exc_value, traceback):
        elapsed = self._tschrono.read_ms()
        # wdt.feed()
        if exc_type:
            self.logger.warning("%s failed (%d ms). %s: %s", self.desc, elapsed, exc_type.__name__, exc_value)
            if self.suppress_exception:
                return True
        else:
            self.logger.info("%s OK (%f ms)", self.desc, elapsed)

class LTE:
    def __init__(self):
        self._lte = None
        self._sql = None
        self.connected = False
        self.type = 'RADIO_LTE'

    def connect(self):
        def send_at_cmd_pretty(cmd):
            _logger.info('> %s', cmd)
            response = self._lte.send_at_cmd(cmd)
            if response != None:
                lines = response.split('\r\n')
                for line in lines:
                    if len(line.strip()) != 0:
                        _logger.info('<< %s', line)
            else:
                _logger.info('<> No response.')
            return response

        tschrono = Timer.Chrono()
        tschrono.start()

        with TimedStep("LTE object init", logger=_logger):
            # network.LTE.reconnect_uart()
            self._lte = network.LTE()
            # self._lte.reconnect_uart()

        with TimedStep("LTE reset", logger=_logger):
            self._lte.reset()
        #     self._lte.send_at_cmd('AT^RESET')

        with TimedStep("LTE network init", logger=_logger):
            self._lte.init()

        with TimedStep('LTE provisioning', logger=_logger):
            send_at_cmd_pretty('AT+CFUN=0')
            # lte.send_at_cmd('AT!="clearscanconfig"')
            # lte.send_at_cmd("AT!=\"RRC::addscanfreq band=8 dl-earfcn=3740\"")
            send_at_cmd_pretty('AT+CGDCONT=1,"IP","%s"' % 'telenor.iot')
            send_at_cmd_pretty('AT+CFUN=1')
            send_at_cmd_pretty('AT+CSQ')

        with TimedStep("LTE attach", logger=_logger):
            self._lte.attach()
            # self._lte.attach(apn='telenor.iot')

            try:
                while True:
                    # wdt.feed()
                    if self._lte.isattached(): 
                        break
                    
                    if tschrono.read_ms() > 300 * 1000: 
                        raise TimeoutError("Timeout during LTE attach")
                    
                    time.sleep_ms(250)
            finally:
                try:
                    self._sql = self.get_signal_strength()['rssi_dbm']
                    _logger.info("LTE attached: %s. Signal quality %s", self._lte.isattached(), self._sql)
                except Exception as e:
                    _logger.exception("While trying to measure and log signal strength: {}".format(e))

        tschrono.reset()
        with TimedStep("LTE connect", logger=_logger):
            self._lte.connect()
            while True:
                # wdt.feed()
                if self._lte.isconnected():
                    self.connected = True
                    break
                if tschrono.read_ms() > 120 * 1000:
                    self.deinit()
                    raise TimeoutError("Timeout during LTE connect")
                
                time.sleep_ms(250)

    def deinit(self):
        self._sql = None
        self.connected = False

        if self._lte is None:
            self._lte = network.LTE()

        try:
            if self._lte.isconnected():
                with TimedStep("LTE disconnect", logger=_logger):
                    self._lte.disconnect()

            if self._lte.isattached():
                with TimedStep("LTE detach", logger=_logger):
                    self._lte.detach()

        finally:
            with TimedStep("LTE deinit", logger=_logger):
                self._lte.deinit()

        self._lte = None

    def get_signal_strength(self):
        output = self._lte.send_at_cmd("AT+CSQ")
        prefix = "\r\n+CSQ: "
        suffix = "\r\n\r\nOK\r\n"
        rssi_raw, ber_raw, rssi_dbm = None, None, None
        if output.startswith(prefix) and output.endswith(suffix):
            output = output[len(prefix):-len(suffix)]
            try:
                rssi_raw, ber_raw = output.split(",")
                rssi_raw, ber_raw = int(rssi_raw), int(ber_raw)
                rssi_dbm = -113 + (rssi_raw * 2)
            except:
                pass

        return {"rssi_raw": rssi_raw, "ber_raw": ber_raw, "rssi_dbm": rssi_dbm}

class NBIOTTCPSocket:

    def __init__(self, nb: NBIOT, timeout=120.0):
        self.nb = nb
        self.host = None
        self.port = None
        self.profile_id = 0
        self.timeout = timeout
        self.response_received = False
        if self.nb.connected is False:
            self.nb.connect()

    def connect(self, address: Tuple[str, int]):
        self.response_received = False
        if self.host is None:
            self.host, self.port = address

        client_pattern = '\+CSOC: ([0-9]+)'
        status, data = self.nb.execute_cmd('AT+CSOC=1,1,1', client_pattern, [1])
        if not status:
            raise NBIOTTCPSocketError('Error while creating TCP socket!')

        self.profile_id = int(data[0])
        status, _ = self.nb.execute_cmd('AT+CSOCON={},{},"{}"'.format(self.profile_id, self.port, self.host))
        if not status:
            raise NBIOTTCPSocketError('Error while establishing connection!')

    def send(self, data: bytes, flags: int = ...):
        data = ubinascii.hexlify(data)
        data = data.decode()
        data_len = len(data)
        if data_len > 1024:
            data = [data[i:i+1024] for i in range(0, data_len, 1024)]
            for part in data:
                status, _ = self.nb.execute_cmd('AT+CSOSEND={},{},{}'.format(self.profile_id, len(part), part))
                if not status:
                    raise NBIOTTCPSocketError('Socket error!')
        else:
            status, _ = self.nb.execute_cmd('AT+CSOSEND={},{},{}'.format(self.profile_id, len(data), data))

        if status:
            return data_len / 2
        
        return 0

    def recv(self, bufsize: int, flags: int = ...):
        data = bytearray()
        if not self.response_received:
            try:
                status, response = self._read_detached_response('+CSONMI:')
            except TimeoutError:
                return data

            if status:
                for r in response:
                    data.extend(ubinascii.unhexlify(r))
                self.response_received = True
        
        return data

    def close(self):
        self.response_received = False
        self.nb.execute_cmd('AT+CSOCL={}'.format(self.profile_id))

    def _read_detached_response(self, expected_prefix, timeout=30.0):
        expected_line = None
        status = False

        tschrono = Timer.Chrono()
        tschrono.start()
        expected_response = []

        while True:
            x = self.nb.serial.readline()

            if tschrono.read_ms() > timeout * 1000: 
                raise TimeoutError("NBIOT _read_response timeout!")

            if x is None:
                continue

            try:
                x = x.decode()
            except UnicodeError:
                continue

            x = x.replace('\r', '').replace('\n', '')

            if len(x) == 0:
                time.sleep(0.1)
                continue

            # it prints only 75 characters read from serial
            _logger.debug("<-- {}".format((x[:75]) + '..' if len(x) > 75 else x))
            # _logger.debug("<-- {}".format(x))
            tschrono.reset()

            if x.find(expected_prefix) >= 0:
                expected_line = x.replace(' ', '').replace('"', '')
                expected_line = expected_line.split(',')
                expected_response.append(expected_line[2])
                status = True
                continue

            if x.find('+CSOERR:') >= 0:
                break

        return status, expected_response

class NBIOTUDPSocket:

    def __init__(self, nb: NBIOT, timeout=10.0):
        self.nb = nb
        self.address = None
        self.profile_id = -1
        self.timeout = timeout
        self.response_received = False
        if self.nb.connected is False:
            self.nb.connect()

    def sendto(self, data: bytes, address: Tuple[str, int]):
        self.address = address
        if self.profile_id < 0:
            self._connect(address)

        data = ubinascii.hexlify(data)
        data = data.decode()
        data_len = len(data)
        status, _ = self.nb.execute_cmd('AT+CSOSEND={},{},{}'.format(self.profile_id, len(data), data), timeout=self.timeout)

        if status:
            return data_len / 2
        
        return 0

    def recvfrom(self, bufsize: int, flags: int = ...):
        data = bytearray()
        try:
            status, response = self._read_detached_response('+CSONMI:', self.timeout)
        except TimeoutError:
            return data, self.address

        if status:
            for r in response:
                data.extend(ubinascii.unhexlify(r))
        
        return data, self.address

    def setblocking(self, flag: bool):
        pass

    def close(self):
        self.response_received = False
        self.nb.execute_cmd('AT+CSOCL={}'.format(self.profile_id))
        self.profile_id = -1
        self.address = None

    def _connect(self, address: Tuple[str, int]):
        self.response_received = False

        client_pattern = '\+CSOC: ([0-9]+)'
        status, data = self.nb.execute_cmd('AT+CSOC=1,2,1', client_pattern, [1])
        if not status:
            raise NBIOTUDPSocketError('Error while creating UDP socket!')

        self.profile_id = int(data[0])
        status, _ = self.nb.execute_cmd('AT+CSOCON={},{},"{}"'.format(self.profile_id, self.address[1], self.address[0]))
        if not status:
            raise NBIOTUDPSocketError('Error while establishing connection!')

    def _read_detached_response(self, expected_prefix, timeout=30.0):
        expected_line = None
        status = False

        tschrono = Timer.Chrono()
        tschrono.start()
        expected_response = []

        while True:
            x = self.nb.serial.readline()

            if tschrono.read_ms() > timeout * 1000: 
                raise TimeoutError("NBIOT _read_response timeout!")

            if x is None:
                continue

            try:
                x = x.decode()
            except UnicodeError:
                continue

            x = x.replace('\r', '').replace('\n', '')

            if len(x) == 0:
                time.sleep(0.1)
                continue

            # it prints only 75 characters read from serial
            _logger.debug("<-- {}".format((x[:75]) + '..' if len(x) > 75 else x))
            # _logger.debug("<-- {}".format(x))
            tschrono.reset()

            if x.find(expected_prefix) >= 0:
                expected_line = x.replace(' ', '').replace('"', '')
                expected_line = expected_line.split(',')
                expected_response.append(expected_line[2])
                status = True
                break

            if x.find('+CSOERR:') >= 0:
                break

        return status, expected_response

class NBIOTCoAPSocket:

    def __init__(self, nb: NBIOT, host_ip, host_port, timeout=10.0, reusable=False):
        self.nb = nb
        self.host_ip = host_ip
        self.host_port = host_port
        self.coap_profile_id = 0
        self.response_data = bytearray()
        self.reusable = reusable
        self.timeout = timeout
        if self.nb.connected is False:
            self.nb.connect()
        
        self._create_client()
    
    def sendto(self, data: bytes, address: Tuple[str, int]):
        self.response_data = bytearray()
        msg_pattern = '\+CCOAPNMI: {},([0-9]+),(.*)'.format(self.coap_profile_id)
        data = ubinascii.hexlify(data)
        data = data.decode()
        status, response = self.nb.execute_cmd('AT+CCOAPSEND={},{},"{}"'.format(
            # self.coap_profile_id, int(len(data) / 2), data), msg_pattern, timeout=20.0
            self.coap_profile_id, int(len(data) / 2), data), msg_pattern, timeout=self.timeout
        )
        if status and response is not None:
            _logger.debug('[NBIOTCoAPSocket] Sent {} bytes!'.format(int(len(data) / 2)))
            r_data = response[2]
            r_data = r_data.encode()
            r_data = ubinascii.unhexlify(r_data)
            self.response_data = r_data

            return int(len(data) / 2)

        raise NBIOTCoAPSocketError

    def recvfrom(self, bufsize: int, flags: int = ...):
        if len(self.response_data) > 0:
            _logger.debug('[NBIOTCoAPSocket] Received {} bytes!'.format(int(len(self.response_data))))

            return self.response_data, (self.host_ip, self.host_port)

        return bytearray(), (self.host_ip, self.host_port)

    def setblocking(self, flag: bool):
        pass

    def close(self):
        if not self.reusable:
            self.nb.execute_cmd('AT+CCOAPDEL={}'.format(self.coap_profile_id))

    def _create_client(self):
        coapnew_pattern = '\+CCOAPNEW: ([0-9]+)'
        status, response = self.nb.execute_cmd('AT+CCOAPNEW="{}",{},{}'.format(self.host_ip, self.host_port, self.coap_profile_id), coapnew_pattern, expected_index=[1])
        if not status:
            raise NBIOTCoAPSocketError('CoAP client creation failed!')
            
        self.coap_profile_id = int(response[0])

class NBIOTMQTTClient:
    def __init__(self, nb: NBIOT, client_id, host_ip, host_port, user = None, password = None):
        self.nb = nb
        self.host_ip = host_ip
        self.host_port = host_port
        self.mqtt_profile_id = -1
        self.pid = -1
        self.cb = None
        self.user = user
        self.pswd = password
        self.client_id = client_id
        self.connected = False

        if self.nb.connected is False:
            self.nb.connect()

    def connect(self):
        if self.mqtt_profile_id < 0:
            self._create_client()
        cmd = 'AT+CMQCON={},4,"{}",600,1,0,"{}","{}"'.format(self.mqtt_profile_id, self.client_id, self.user, self.pswd)
        status, response = self.nb.execute_cmd(cmd)
        if not status:
            raise MQTTClientError('Connection to MQTT broker failed!')

        self.connected = True

    def publish(self, topic, msg, retain = False, qos = 0):
        if not self.connected:
            raise MQTTClientError('connect() has to be called first!')

        msg = ubinascii.hexlify(msg)
        msg = msg.decode()
        retain = 0 if not retain else 1
        # cmqpub_pattern = '\+CMQPUB:'
        cmd = 'AT+CMQPUB={},"{}",{},{},0,{},"{}"'.format(self.mqtt_profile_id, topic, qos, retain, len(msg), msg)
        status, _ = self.nb.execute_cmd(cmd, timeout=30.0)
        if not status:
            raise MQTTClientError('Publish failed!')

    def subscribe(self, topic, qos = 0):
        if not self.connected:
            raise MQTTClientError('connect() has to be called first!')

        status, _ = self.nb.execute_cmd('AT+CMQSUB={},"{}",{}'.format(self.mqtt_profile_id, topic, qos))
        if not status:
            raise MQTTClientError('Subscribe failed!')

    def unsubscribe(self, topic):
        if not self.connected:
            raise MQTTClientError('connect() has to be called first!')

        status, _ = self.nb.execute_cmd('AT+CMQUNSUB={},"{}"'.format(self.mqtt_profile_id, topic))
        if not status:
            raise MQTTClientError('Unsubscribe failed!')

    def wait_msg(self):
        if not self.connected:
            raise MQTTClientError('connect() has to be called first!')

        status, response = self.nb._read_detached_response('+CMQPUB', timeout=60.0)
        self.cb(response[1], ubinascii.unhexlify(response[6]))

    def disconnect(self):
        if not self.connected:
            raise MQTTClientError('connect() has to be called first!')

        self.nb.execute_cmd('AT+CMQDISCON={}'.format(self.mqtt_profile_id))
        self.connected = False
        self.mqtt_profile_id = -1

    def set_callback(self, f):
        self.cb = f

    def _create_client(self):
        if self.mqtt_profile_id < 0:
            # create new MQTT profile
            cmqnew_pattern = '\+CMQNEW: (\d+)'
            status, response = self.nb.execute_cmd('AT+CMQNEW="{}",{},60000,1024'.format(self.host_ip, self.host_port), cmqnew_pattern, [1])
            if not status:
                raise MQTTClientError('MQTT profile creation failed!')

            self.mqtt_profile_id = int(response[0])

class NBIOT:
    def __init__(self):
        self._sql = None
        self.connected = False
        self.type = 'RADIO_NBIOT'
        self.serial = serial(1, baudrate=115200, pins=('P3', 'P8'), rx_buffer_size=4096)
        self.power_pin = Pin('P4', mode=Pin.OUT, pull=Pin.PULL_UP)
        self._cmd = None

    def connect(self):
        while True:
            try:
                status, error = self._enable()
                if status is True:
                    break
            except TimeoutError:
                time.sleep(2)
                continue
        # set radio to minimum functionality state in order to set APN
        self.execute_cmd('AT+CFUN=0')
        # set APN
        self.execute_cmd('AT*MCGDEFCONT="IP","telenor.iot')
        # set back full radio functionality
        cfun_pattern = '\+CPIN: READY'
        self.execute_cmd('AT+CFUN=1', cfun_pattern)
        # attach to the operator
        attach_pattern = '\+CGCONTRDP:.*\"telenor.iot\",\"([0-9]+.[0-9]+.[0-9]+.[0-9]+.[0-9]+.[0-9]+.[0-9]+.[0-9]+)\".*'
        while True:
            try:
                self.execute_cmd('AT+CGCONTRDP', attach_pattern, timeout=2.0)
                break
            except TimeoutError:
                continue

        # check COPS
        cops_pattern = '\+COPS: 0,2,\"24201\",9'
        self.execute_cmd('AT+COPS?', cops_pattern)
        # check DNS
        dns_check_domain = 'www.google.no'
        dns_pattern = '\+CDNSGIP:.*,\"{}",\"([0-9]+.[0-9]+.[0-9]+.[0-9]+)\"'.format(dns_check_domain.replace('.', '\.'))
        dns_status, dns_data = self.execute_cmd('AT+CDNSGIP="{}"'.format(dns_check_domain), dns_pattern)
        if dns_status:
            _logger.info('[{}]: {}'.format(dns_data[1], dns_data[2]))
        # check signal quality
        sqn = self.get_signal_strength()
        _logger.info('Signal quality: {}dbm'.format(sqn[2]))
        self.connected = True

    def deinit(self):
        self.execute_cmd('AT+CPOWD=1', last_line='NORMAL POWER DOWN')
        self.connected = False

    def ping(self, host, count=5, timeout=20.0):
        def _read_ping_response(number=4, timeout=20.0):
            ping_prefix = '+CIPPING: '
            status = False
            cmd_line = False
            reply_time = []
            reply_nr = 0

            tschrono = Timer.Chrono()
            tschrono.start()

            while True:
                x = self.serial.readline()

                if tschrono.read_ms() > timeout * 1000: 
                    raise TimeoutError("NBIOT _read_response timeout!")

                if x is None:
                    continue

                try:
                    x = x.decode()
                except UnicodeError:
                    continue

                x = x.replace('\r', '').replace('\n', '')

                if len(x) == 0:
                    time.sleep(0.1)
                    continue

                tschrono.reset()
                _logger.debug("<-- %s" % x)

                if x == 'OK':
                    status = True
                    continue

                if x == 'ERROR':
                    status = False
                    break

                if x == self._cmd:
                    cmd_line = True
                    continue

                if x.find(ping_prefix) >= 0:
                    x = x.replace(ping_prefix, '')
                    tmp_ping = x.split(',')
                    reply_nr = int(tmp_ping[0])
                    reply_time.append('icmp_seq={}, ttl={}, time={} ms'.format(reply_nr, tmp_ping[3], int(tmp_ping[2])*100))
                    _logger.debug('Reply nr: {}' .format(reply_nr))

                if reply_nr == number:
                    break

            return status and cmd_line, reply_time

        # check DNS
        dns_pattern = '\+CDNSGIP:.*,\"{}",\"([0-9]+.[0-9]+.[0-9]+.[0-9]+)\"'.format(host.replace('.', '\.'))
        dns_status, dns_data = self.execute_cmd('AT+CDNSGIP="{}"'.format(host), dns_pattern)
        if not dns_status:
            return
        
        _logger.info('[{}]: {}'.format(dns_data[1], dns_data[2]))
        ping_cmd = 'AT+CIPPING={},{},32,{}'.format(dns_data[2], count, int(timeout * 10))
        self._send_cmd(ping_cmd)
        self._cmd = ping_cmd
        status, ping_response = _read_ping_response(count, timeout)
        if not status:
            return

        for ping in ping_response:
            _logger.info('64 bytes from {}: {}'.format(dns_data[2], ping))

    def get_signal_strength(self):
        # check signal quality
        csq_pattern = '\+CSQ: ([0-9]+),([0-9]+)'
        status, signal_search = self.execute_cmd('AT+CSQ', csq_pattern, expected_index=[1,2])
        if status:
            rssi_raw, ber_raw = signal_search[0], signal_search[1]

            rssi_dbm = None
            try:
                rssi_raw, ber_raw = int(rssi_raw), int(ber_raw)
                rssi_dbm = -110 + (rssi_raw * 2)
            except:
                pass

            return rssi_raw, ber_raw, rssi_dbm

        return 0, 0, 0

    def execute_cmd(self, cmd, expected_line=None, expected_index=None, last_line='OK', timeout=5.0):
        self._cmd = cmd
        self._send_cmd(cmd)
        status, expected_value = self._read_response(expected_line, expected_index, last_line, timeout)
        _logger.info("<--- %s\n" % 'CMD_OK' if status else 'CMD_ERROR')

        return status, expected_value

    def _enable(self):
        def power_on():
            self.power_pin.value(0)
            time.sleep(0.9)
            self.power_pin.value(1)
            time.sleep(2)

        power_on()
        return self.execute_cmd('AT')

    def _send_cmd(self, cmd):
        _logger.info("---> {}".format(cmd[:75] if len(cmd) > 75 else cmd))
        full_cmd = "%s\r\n" % cmd

        self.serial.write(full_cmd)

    def _read_response(self, expected_pattern=None, expected_index=None, last_line='OK', timeout=5.0):
        expected_line = None
        last_line_found = False
        status = False
        pattern = None
        cmd_line = False
        executed_cmd = self._cmd[:75] if len(self._cmd) > 75 else self._cmd

        tschrono = Timer.Chrono()
        tschrono.start()

        if expected_pattern is not None:
            pattern = re.compile(expected_pattern)

        while not last_line_found or not cmd_line or not status:
            x = self.serial.readline()

            if tschrono.read_ms() > timeout * 1000: 
                raise TimeoutError("NBIOT _read_response timeout!")

            if x is None:
                continue

            try:
                x = x.decode()
            except UnicodeError:
                continue

            x = x.replace('\r', '').replace('\n', '')

            if len(x) == 0:
                time.sleep(0.1)
                continue

            # it prints only 75 characters read from serial
            _logger.debug("<-- {}".format((x[:75]) + '..' if len(x) > 75 else x))

            if x == 'OK':
                status = True
                # print('STATUS: OK')

            if x == 'NORMAL POWER DOWN' and self._cmd.find('AT+CPOWD') < 0:
                return False, -1

            if x == 'ERROR':
                status = False
                break

            if x.find(executed_cmd) >= 0:
                cmd_line = True
                # print('CMD_LINE: OK')

            if expected_line is None and expected_pattern is not None:
                # string might be too big to process
                # @see: https://github.com/micropython/micropython/issues/2451
                try:
                    search = pattern.match(x)
                except RuntimeError:
                    _logger.warning('re is not able to process given input. Handling special case!')
                    lines = [x[i:i+100] for i in range(0, len(x), 100)]
                    for line in lines:
                        search = pattern.match(line)
                        if search is not None and len(search.group(0)) > 0:
                            expected_line = x.split(',')
                            last_line_found = True
                            status = True


                if search is None:
                    continue

                if len(search.group(0)) > 0:
                    expected_line = []
                    if expected_index is not None:
                        for i in expected_index:
                            expected_line.append(search.group(i))
                    else:
                        expected_line = x.split(',')
                    last_line_found = True
                    # status = True

            if expected_pattern is None and x.find(last_line) >= 0:
                last_line_found = True
                status = True
                # print('STATUS & LAST_LINE: OK')

        return status, expected_line

    def _read_detached_response(self, expected_prefix, timeout=30.0):
        expected_line = None
        status = False

        tschrono = Timer.Chrono()
        tschrono.start()

        while True:
            x = self.serial.readline()

            if tschrono.read_ms() > timeout * 1000: 
                raise TimeoutError("NBIOT _read_response timeout!")

            if x is None:
                continue

            try:
                x = x.decode()
            except UnicodeError:
                continue

            x = x.replace('\r', '').replace('\n', '')

            if len(x) == 0:
                time.sleep(0.1)
                continue

            # it prints only 75 characters read from serial
            # _logger.debug("<-- {}".format((x[:75]) + '..' if len(x) > 75 else x))
            _logger.debug("<-- {}".format(x))

            if x.find(expected_prefix) >= 0:
                expected_line = x.replace(' ', '').replace('"', '')
                expected_line = expected_line.split(',')
                status = True
                break

        return status, expected_line

class WLAN:
    def __init__(self):
        self._ssid = None
        self._sql = None
        self._wlan = None
        self.type = 'RADIO_WLAN'
        self.connected = False

    def connect(self):
        tschrono = Timer.Chrono()
        self._wlan = network.WLAN(mode=network.WLAN.STA)
        WIFI_TO_CONNECT = {'NETWORK': 'PASSWORD'}
        while True:
            nets = self._wlan.scan()
            for net in nets:
                if net.ssid in WIFI_TO_CONNECT:
                    self._sql = net.rssi
                    self._ssid = net.ssid

                    tschrono.start()
                    _logger.info("WLAN network found: '%s'. Signal quality %s", self._ssid, self._sql)
                    with TimedStep('WLAN connect', logger=_logger):
                        self._wlan.connect(net.ssid, auth=(net.sec, WIFI_TO_CONNECT[net.ssid]), timeout=5000)
                        while not self._wlan.isconnected():
                            if tschrono.read_ms() > 20 * 1000: 
                                raise TimeoutError("Timeout during WiFi connect", logger=_logger)
                            time.sleep_ms(250)

                    self.connected = True
                    return


    def deinit(self):
        self.connected = False
        self._ssid = None
        self._sql = None

        if self._wlan is not None:
            with TimedStep("WLAN deinit", logger=_logger):
                self._wlan.deinit()
