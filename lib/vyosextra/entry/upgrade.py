#!/usr/bin/env python3

import os
import socket
import shutil
import argparse
from datetime import datetime

from threading import Thread
from http.server import HTTPServer, SimpleHTTPRequestHandler

from vyosextra import cmd
from vyosextra.config import Config

from vyosextra.entry.download import makeup
from vyosextra.entry.download import fetch


class Command(cmd.Command):
	def upgrade(self, where, url):
		# on my local VM which goes to sleep when I close my laptop
		# time can easily get out of sync, which prevent apt to work
		now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
		self.ssh(where, f"sudo date -s '{now}'")
		self.ssh(where, f"printf 'yes\n\nyes\nyes\nyes\n' | sudo /opt/vyatta/sbin/install-image {url}")
		self.ssh(where, 'printf 1 | /opt/vyatta/bin/vyatta-boot-image.pl --select')
		self.ssh(where, 'sudo reboot')


def start_server(path, file, port):
	class Handler(SimpleHTTPRequestHandler):
		def do_GET(self):
			if self.path != f'/{file}':
				return

			with open(os.path.join(path, file), 'rb') as f:
				fs = os.fstat(f.fileno())

				self.send_response(200)
				self.send_header("Content-type", "application/octet-stream")
				self.send_header("Content-Disposition", f'attachment; filename="{file}"')
				self.send_header("Content-Length", str(fs.st_size))
				self.end_headers()

				shutil.copyfileobj(f, self.wfile)

	os.chdir(path)
	httpd = HTTPServer(('', port), Handler)
	httpd.serve_forever()
	sys.exit(1)

def web(name, location, port):
	if not os.path.exists(location):
		fetch()

	daemon = Thread(
		name='serve VyOS',
		target=start_server,
		args=(os.path.dirname(location), name, port)
	)

	daemon.setDaemon(True)
	daemon.start()

def upgrade():
	parser = argparse.ArgumentParser(description='upgrade router to latest VyOS image')
	parser.add_argument("machine", help='machine on which the action will be performed')

	parser.add_argument('-i', '--ip', type=str, help="ip to bind the webserver")
	parser.add_argument('-p', '--port', type=int, help="port to bind the webserver", default=8888)

	args = parser.parse_args()

	cmds = Command()

	ip = args.ip if args.ip else socket.gethostbyname(socket.gethostname())
	port = args.port

	name, location, url = makeup('')
	daemon = web(name, location, port)

	print(f'http://{ip}:{port}/{name}')
	web(name, location, port)
	cmds.upgrade(args.machine, f'http://{ip}:{port}/{name}')

if __name__ == '__main__':
	upgrade()