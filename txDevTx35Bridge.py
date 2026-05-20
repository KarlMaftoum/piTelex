#!/usr/bin/env python3
"""piTelex device module: TX35 Exchange Bridge.

This module runs inside piTelex and bridges between piTelex's internal
message bus and the tx35exchd exchange daemon via localhost TCP.

piTelex bus protocol:
  - read() returns ASCII characters or \\x1b escape commands
  - write(a, source) receives ASCII characters or \\x1b escape commands
  - Escape commands: \\x1bAT (connect), \\x1b#NUMBER (dial), \\x1bST (stop)
  - Regular characters: ASCII text (piTelex handles Baudot conversion internally)

Install: copy this file into the piTelex source directory, then enable
the device in your piTelex config under "devices":

    "tx35bridge": {
        "type": "tx35bridge",
        "enable": true,
        "port": 2343
    }

Companion daemon: https://github.com/YOUR-USERNAME/tx35exchd
"""

import socket
import threading
import time
import logging

try:
    import txBase
except ImportError:
    # Running outside piTelex for testing
    class _FakeBase:
        def __init__(self): pass
    class txBase:
        TelexBase = _FakeBase

log = logging.getLogger('piTelex.' + __name__)


class TelexTx35Bridge(txBase.TelexBase):
    """piTelex device module bridging to tx35exchd exchange daemon.

    Listens on localhost TCP for connections from the exchange daemon.
    When daemon connects:
      - Receives: 'D<number>\\n' = dial request, 'S\\n' = stop, or ASCII chars to send
      - Sends: ASCII characters received from piTelex bus (from remote telex)
    """

    def __init__(self, **params):
        super().__init__()
        self.id = 'Tx35'
        self.params = params
        self._port = params.get('port', 2343)
        self._server_sock = None
        self._client_sock = None
        self._running = False
        self._rx_buffer = []  # Commands/chars to send to piTelex bus
        self._lock = threading.Lock()
        self._last_feedback_t = 0  # monotonic time of last \x1b~N sent

        # Start listener thread immediately (like other piTelex modules)
        print(f'[TX35 Bridge] Starting on port {self._port}...')
        self._thread = threading.Thread(target=self.thread_function, args=('Tx35',), daemon=True)
        self._thread.start()
        print(f'[TX35 Bridge] Thread started')

    def exit(self):
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
        if self._client_sock:
            try:
                self._client_sock.close()
            except Exception:
                pass

    def thread_function(self, name, *args):
        """Background thread: listen for connections from tx35exchd."""
        self._running = True

        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.settimeout(1.0)
        self._server_sock.bind(('127.0.0.1', self._port))
        self._server_sock.listen(1)
        print(f'[TX35 Bridge] Listening on localhost:{self._port}')
        log.info('TX35 bridge listening on localhost:%d', self._port)

        while self._running:
            try:
                client, addr = self._server_sock.accept()
                log.info('TX35 daemon connected')
                client.settimeout(0.05)
                self._client_sock = client
                self._handle_client()
            except socket.timeout:
                continue
            except (socket.error, OSError) as e:
                if self._running:
                    log.warning('Server error: %s', e)
                    time.sleep(1)

    def _handle_client(self):
        """Handle a single connection from the exchange daemon.

        Protocol:
            Bytes 0x00-0x1F: raw 5-bit Baudot codes (converted to ASCII for piTelex bus)
            Bytes 0x20+: command bytes, collected as line until \\n:
                'D<number>\\n' = dial
                'S\\n' = stop/clear
        """
        self._cmd_buf = ''
        self._in_command = False
        self._baudot_mode = 0  # 0=LTRS, 1=FIGS

        # ITA2 decode tables (same as standard Baudot)
        # ITA2 Baudot decode tables (must be exactly 32 chars each)
        self._ltrs = "\x00E\nA SIU\rDRJNFCKTZLWHYPQOBG\x1bMXV\x1f"
        self._figs = '\x003\n- \'87\r\x054\x07,!:(5")2#6019?&\x1b./;\x1f'

        while self._running and self._client_sock:
            try:
                data = self._client_sock.recv(1024)
                if not data:
                    log.info('TX35 daemon disconnected')
                    break

                for byte in data:
                    if self._in_command:
                        if byte == 0x0A:  # \n = end of command
                            cmd = self._cmd_buf
                            self._in_command = False
                            self._cmd_buf = ''
                            self._process_command(cmd)
                        else:
                            self._cmd_buf += chr(byte)

                    elif byte >= 0x20:
                        # Start of a text command (D, S, etc.)
                        self._in_command = True
                        self._cmd_buf = chr(byte)

                    else:
                        # Raw Baudot code 0x00-0x1F
                        code = byte & 0x1F
                        if code == 0x1F:  # LTRS
                            self._baudot_mode = 0
                        elif code == 0x1B:  # FIGS
                            self._baudot_mode = 1
                        else:
                            # Decode Baudot to ASCII
                            if self._baudot_mode == 0:
                                ch = self._ltrs[code]
                            else:
                                ch = self._figs[code]

                            # Map special codes to piTelex conventions
                            if ch == '\x05':  # ENQ/WRU → piTelex uses @
                                with self._lock:
                                    self._rx_buffer.append('@')
                            elif ch == '\x07':  # BEL → piTelex uses %
                                with self._lock:
                                    self._rx_buffer.append('%')
                            elif ch and (ch >= ' ' or ch in '\r\n'):
                                with self._lock:
                                    self._rx_buffer.append(ch)

            except socket.timeout:
                pass
            except (socket.error, OSError):
                break

        with self._lock:
            self._rx_buffer.append('\x1bST')
        self._client_sock = None

    def _process_command(self, cmd):
        """Process a text command from the daemon."""
        if cmd.startswith('D'):
            number = cmd[1:].strip()
            log.info('Dial request: %s', number)
            with self._lock:
                self._rx_buffer.append('\x1bAT')
            time.sleep(0.2)
            with self._lock:
                for digit in number:
                    self._rx_buffer.append(digit)
            time.sleep(2.5)  # piTelex dial watchdog

        elif cmd.startswith('S'):
            log.info('Stop request')
            with self._lock:
                self._rx_buffer.append('\x1bST')

    def read(self):
        """Called by piTelex MCP to get data/commands from this module.

        Returns:
            str: ASCII character, escape command, or empty string.
        """
        with self._lock:
            if self._rx_buffer:
                return self._rx_buffer.pop(0)
        return ''

    def idle2Hz(self):
        """Called by piTelex MCP at 2 Hz. Send printer buffer feedback so
        piTelex's ACK counter can advance and remote clients (WinTLX, M100,
        etc.) don't stall with a 'remote printer full' indication.

        We report print_buf_len=0 since the daemon buffers in its own queue
        and prints asynchronously at 50 baud. Without this feedback, piTelex
        never learns the banner has been printed and ACK stays at -24.
        """
        if self._client_sock is not None:
            now = time.monotonic()
            if now - self._last_feedback_t >= 1.0:
                self._last_feedback_t = now
                with self._lock:
                    self._rx_buffer.append('\x1b~0')

    def write(self, a, source=None):
        """Called by piTelex MCP when data arrives for this module.

        For incoming calls: if no daemon connection exists, connect to daemon
        and notify it of the incoming call. Then forward data.

        Args:
            a: ASCII character or escape command string.
            source: originating module ID.
        """
        # Detect incoming call: piTelex sends data but daemon isn't connected
        if self._client_sock is None:
            if a and not a.startswith('\x1b'):
                # Incoming call — connect to daemon
                print(f'[TX35 Bridge] Incoming call detected, connecting to daemon...')
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(3)
                    sock.connect(('127.0.0.1', self._port + 1))  # port 2344
                    sock.settimeout(0.05)
                    self._client_sock = sock
                    # Notify daemon this is an incoming call
                    self._client_sock.sendall(b'INCOMING\n')
                    print(f'[TX35 Bridge] Connected to daemon for incoming call')
                    # Start a background thread to receive from daemon
                    threading.Thread(target=self._handle_client, daemon=True).start()
                except (socket.error, OSError) as e:
                    print(f'[TX35 Bridge] Failed to connect to daemon: {e}')
                    return

        # Handle piTelex escape commands
        if a and a.startswith('\x1b'):
            if a in ('\x1bST', '\x1bZ', '\x1bZZ'):
                # Remote disconnected — close connection to daemon
                print(f'[TX35 Bridge] Remote disconnect: {repr(a)}')
                if self._client_sock:
                    try:
                        self._client_sock.close()
                    except Exception:
                        pass
                    self._client_sock = None
            elif a == '\x1bA':
                # Printer start request — respond immediately (TX35 is always ready).
                # Follow up with \x1b~0 so piTelex knows printer buffer is empty
                # and can update ACK counter to let remote send data.
                with self._lock:
                    self._rx_buffer.append('\x1bAA')
                    self._rx_buffer.append('\x1b~0')
            return

        # Forward ASCII character to daemon as raw Baudot
        if a and len(a) == 1 and self._client_sock:
            try:
                self._client_sock.sendall(a.encode('ascii', errors='replace'))
            except (socket.error, OSError):
                self._client_sock = None
