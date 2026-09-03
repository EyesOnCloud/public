import argparse, http.server, time
p = argparse.ArgumentParser(); p.add_argument("--mode", choices=["hang", "flaky", "fail"], required=True)
p.add_argument("--fail-count", type=int, default=2)
args = p.parse_args()
calls = {"n": 0}
class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        calls["n"] += 1
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        print(f"[stub:{args.mode}] request #{calls['n']}", flush=True)
        if args.mode == "hang":
            time.sleep(8); return
        elif args.mode == "flaky":
            self.send_response(500 if calls["n"] <= args.fail_count else 200); self.end_headers()
        elif args.mode == "fail":
            self.send_response(500); self.end_headers()
    def log_message(self, *a): pass
http.server.ThreadingHTTPServer(("127.0.0.1", 9), Handler).serve_forever()
