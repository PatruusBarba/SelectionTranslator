"""Minimal mock OpenAI-compatible /v1/chat/completions server for testing."""

import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MOCK-LLM] %(message)s")
log = logging.getLogger(__name__)


class MockHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        messages = body.get("messages", [])
        user_text = ""
        for msg in messages:
            if msg.get("role") == "user":
                user_text = msg.get("content", "")

        log.info("Received translation request: %s", user_text[:120])

        translated = f"[TRANSLATED] {user_text[-200:]}"

        response = {
            "id": "mock-001",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": translated},
                    "finish_reason": "stop",
                }
            ],
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        resp_bytes = json.dumps(response).encode()
        self.send_header("Content-Length", str(len(resp_bytes)))
        self.end_headers()
        self.wfile.write(resp_bytes)

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        body = json.dumps({"status": "ok"}).encode()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        log.info(format, *args)


if __name__ == "__main__":
    port = 1234
    server = HTTPServer(("127.0.0.1", port), MockHandler)
    log.info("Mock LLM server running on http://127.0.0.1:%d/v1", port)
    server.serve_forever()
