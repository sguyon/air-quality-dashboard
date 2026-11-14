"""setup.py --start (14 Nov, after Codex ran the live check before the background app was up)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import setup  # noqa: E402

SERVER = """#!/bin/sh
exec "$1" -c "
import http.server, os
print('Paste your AirGradient token here: http://localhost:%s/?setup=abc' % os.environ['PORT'], flush=True)
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers()
    def log_message(self, *a): pass
http.server.HTTPServer(('127.0.0.1', int(os.environ['PORT'])), H).serve_forever()
" 
"""


def fake_root(tmp_path, script):
    run = tmp_path / "scripts" / "run.sh"
    run.parent.mkdir()
    run.write_text(script)
    run.chmod(0o755)
    return tmp_path


def test_start_waits_for_the_app_and_prints_the_address_and_link(tmp_path, capsys):
    root = fake_root(tmp_path, SERVER.replace('"$1"', f'"{sys.executable}"'))
    env = {"PORT": "5641", "PATH": "/usr/bin:/bin"}
    assert setup.start_app(env, root) == 0
    out = capsys.readouterr().out
    assert "Started: http://localhost:5641" in out and "?setup=abc" in out
    import urllib.request
    assert urllib.request.urlopen("http://127.0.0.1:5641/").status == 200
    import os, signal, subprocess
    pid = subprocess.run(["lsof", "-ti", ":5641"], capture_output=True, text=True).stdout.split()
    for p in pid:
        os.kill(int(p), signal.SIGTERM)


def test_a_bare_live_checks_the_port_start_chose(tmp_path):
    assert setup.started_port({"PORT": "5555"}, tmp_path) == 5555
    (tmp_path / "app.port").write_text("5601\n")
    assert setup.started_port({"PORT": "5555"}, tmp_path) == 5601


def test_start_says_so_when_the_app_dies(tmp_path, capsys):
    root = fake_root(tmp_path, "#!/bin/sh\necho boom >&2\nexit 3\n")
    assert setup.start_app({"PORT": "5642", "PATH": "/usr/bin:/bin"}, root) == 1
    out = capsys.readouterr().out
    assert "stopped right after starting" in out and "boom" in out
