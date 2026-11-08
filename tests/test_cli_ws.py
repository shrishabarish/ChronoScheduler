import unittest
import os
import sys
import io
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.server.ws_server import LightweightWebSocketServer
from src.cli import cmd_inspect, cmd_profiles, cmd_bench

class TestWebSocketServer(unittest.TestCase):
    def setUp(self):
        self.server = LightweightWebSocketServer(host="127.0.0.1", port=8766)

    def test_handshake_response_generation(self):
        key = "dGhlIHNhbXBsZSBub25jZQ=="
        response = self.server._create_handshake_response(key)
        self.assertIn(b"HTTP/1.1 101 Switching Protocols", response)
        self.assertIn(b"Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=", response)

    def test_ws_frame_encoding_short(self):
        msg = "Hello World"
        frame = self.server._encode_ws_frame(msg)
        self.assertEqual(frame[0], 0x81)  # FIN + Text
        self.assertEqual(frame[1], len(msg))
        self.assertEqual(frame[2:].decode("utf-8"), msg)

    def test_ws_frame_encoding_medium(self):
        msg = "A" * 200
        frame = self.server._encode_ws_frame(msg)
        self.assertEqual(frame[0], 0x81)
        self.assertEqual(frame[1], 126)
        self.assertEqual(len(frame), 4 + 200)

class TestCLICommands(unittest.TestCase):
    def test_cmd_inspect_empty(self):
        stdout_buf = io.StringIO()
        sys.stdout = stdout_buf
        try:
            cmd_inspect(None)
        finally:
            sys.stdout = sys.__stdout__
        output = stdout_buf.getvalue()
        self.assertIn("ChronoSched Learned Dependency Graph", output)

    def test_cmd_profiles_empty(self):
        stdout_buf = io.StringIO()
        sys.stdout = stdout_buf
        try:
            cmd_profiles(None)
        finally:
            sys.stdout = sys.__stdout__
        output = stdout_buf.getvalue()
        self.assertIn("ChronoSched Digital Twin Learned Profiles", output)

    def test_cmd_bench(self):
        stdout_buf = io.StringIO()
        sys.stdout = stdout_buf
        try:
            args = argparse.Namespace(iterations=2)
            cmd_bench(args)
        finally:
            sys.stdout = sys.__stdout__
        output = stdout_buf.getvalue()
        self.assertIn("Empirical Benchmark Complete", output)

if __name__ == "__main__":
    unittest.main()
