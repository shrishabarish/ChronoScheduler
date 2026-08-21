import asyncio
import json
import hashlib
import base64
import struct
import threading
from typing import Set, Any

class LightweightWebSocketServer:
    """
    A zero-dependency RFC 6455 WebSocket server using Python standard library asyncio.
    Allows frontend/index.html to connect instantly without installing external pip packages.
    """
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
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
                data = await reader.read(2048)
                if not data:
                    break
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
