# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""A stand-in coco.v1 server for the Live tab's quiet-probe check (M0 fix A.2).

NOT the robot stack. It answers ``/healthz`` the way a LOCAL
``platform_server`` does (coco.v1 body, open access, and no CORS header,
because a local server has no ``origins`` allowlist), and on ``/ws`` sends a
``welcome`` and answers ``ping`` with ``pong``. That is all the page needs
to reach "connected". Usage: ``python3 stub_stack.py PORT``.
"""

import json
import sys

import tornado.ioloop
import tornado.web
import tornado.websocket


class Health(tornado.web.RequestHandler):
    def get(self):
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({'protocol': 'coco.v1', 'state': 'ready',
                               'live': {'access': 'open'}, 'stub': True}))


class Socket(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self):
        self.write_message(json.dumps({
            'type': 'welcome', 'protocol': 'coco.v1', 'commands': [],
            'limits': {'linear': 0.5, 'angular': 1.2, 'colours': [], 'modes': []},
            'world': None, 'you': 'stub-1'}))

    def on_message(self, message):
        try:
            f = json.loads(message)
        except ValueError:
            return
        if f.get('type') == 'ping':
            self.write_message(json.dumps({'type': 'pong', 't': f.get('t')}))


if __name__ == '__main__':
    port = int(sys.argv[1])
    tornado.web.Application([(r'/healthz', Health), (r'/ws', Socket)]).listen(port, 'localhost')
    print(f'stub coco.v1 on localhost:{port}', flush=True)
    tornado.ioloop.IOLoop.current().start()
