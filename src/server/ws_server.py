import asyncio
import json
import hashlib
import base64
import struct
import threading
from typing import Set, Any, Optional, Callable

class LightweightWebSocketServer:
    """
    A zero-dependency RFC 6455 WebSocket server using Python standard library asyncio.
    Allows frontend/index.html to connect instantly without installing external pip packages.
    """
    def __init__(self, host: str = "127.0.0.1", port: int = 8765, on_client_message: Optional[Callable[[str, Any], None]] = None):
        self.host = host
        self.port = port
        self.on_client_message = on_client_message
        self.clients: Set[asyncio.StreamWriter] = set()
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._server = None
        self._thread = None
        self._lock = threading.Lock()

    def _create_handshake_response(self, key: str) -> bytes:
        guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        accept_key = base64.b64encode(hashlib.sha1((key + guid).encode("utf-8")).digest()).decode("utf-8")
        return (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_key}\r\n\r\n"
        ).encode("utf-8")

    def _encode_ws_frame(self, message: str) -> bytes:
        payload = message.encode("utf-8")
        payload_len = len(payload)
        header = bytearray([0x81])  # FIN + Text frame
        if payload_len <= 125:
            header.append(payload_len)
        elif payload_len <= 65535:
            header.append(126)
            header.extend(struct.pack("!H", payload_len))
        else:
            header.append(127)
            header.extend(struct.pack("!Q", payload_len))
        return bytes(header) + payload

    def _decode_ws_frame(self, data: bytes) -> Optional[str]:
        """Decodes an RFC 6455 masked text frame from a client."""
        if len(data) < 6:
            return None
        # byte 0: fin & opcode
        opcode = data[0] & 0x0F
        if opcode == 0x8:  # Close frame
            return None
        # byte 1: mask & payload len
        masked = (data[1] & 0x80) != 0
        payload_len = data[1] & 0x7F
        offset = 2
        if payload_len == 126:
            if len(data) < 4:
                return None
            payload_len = struct.unpack("!H", data[2:4])[0]
            offset = 4
        elif payload_len == 127:
            if len(data) < 10:
                return None
            payload_len = struct.unpack("!Q", data[2:10])[0]
            offset = 10

        if not masked or len(data) < offset + 4 + payload_len:
            return None

        mask_key = data[offset:offset+4]
        offset += 4
        payload = bytearray(data[offset:offset+payload_len])
        for i in range(len(payload)):
            payload[i] ^= mask_key[i % 4]

        try:
            return payload.decode("utf-8")
        except Exception:
            return None

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            request = await reader.read(4096)
            request_text = request.decode("utf-8", errors="ignore")
            
            # Extract Sec-WebSocket-Key
            key = None
            for line in request_text.split("\r\n"):
                if line.lower().startswith("sec-websocket-key:"):
                    key = line.split(":", 1)[1].strip()
                    break

            if not key:
                writer.close()
                await writer.wait_closed()
                return

            writer.write(self._create_handshake_response(key))
            await writer.drain()

            with self._lock:
                self.clients.add(writer)

            while True:
                data = await reader.read(4096)
                if not data:
                    break
                decoded = self._decode_ws_frame(data)
                if decoded and self.on_client_message:
                    try:
                        msg = json.loads(decoded)
                        self.on_client_message(msg.get("action", ""), msg.get("payload", {}))
                    except Exception:
                        pass
        except Exception:
            pass
        finally:
            with self._lock:
                if writer in self.clients:
                    self.clients.remove(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    def broadcast_sync(self, event_type: str, data: Any):
        if not self.loop or not self.clients:
            return
        payload = json.dumps({"type": event_type, "data": data, "timestamp": asyncio.get_event_loop().time() if self.loop else 0})
        frame = self._encode_ws_frame(payload)
        
        async def _send_all():
            with self._lock:
                active_clients = list(self.clients)
            for writer in active_clients:
                try:
                    writer.write(frame)
                    await writer.drain()
                except Exception:
                    pass

        asyncio.run_coroutine_threadsafe(_send_all(), self.loop)

    async def _run_server(self):
        self.loop = asyncio.get_running_loop()
        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)
        await self._server.serve_forever()

    def start(self):
        def _target():
            asyncio.run(self._run_server())
        self._thread = threading.Thread(target=_target, daemon=True)
        self._thread.start()

