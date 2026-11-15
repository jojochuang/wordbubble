#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wordbubble 本機伺服器：靜態頁 + 試算表／教育部 Track／筆畫數 API。"""

import http.server
import json
import os
import re
import socketserver
import threading
import urllib.parse
import urllib.request

PORT = int(os.environ.get("WORDBUBBLE_PORT", "5002"))
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, code, msg):
        self.send_json(code, {"error": msg})

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/get_stroke_count":
            self.handle_get_stroke_count()
            return
        if path == "/api/sheet_csv":
            self.handle_sheet_csv()
            return
        if path == "/api/moe_stroke":
            self.handle_moe_stroke()
            return

        if path in ("/", ""):
            self.path = "/index.html"
        return super().do_GET()

    def handle_get_stroke_count(self):
        try:
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            char = urllib.parse.unquote((params.get("char") or [""])[0])
            if not char:
                self.send_error_json(400, "缺少參數: char")
                return
            char = char[0]
            char_dir = os.path.join(DIRECTORY, "svg", char)
            if not os.path.isdir(char_dir):
                self.send_error_json(404, f"找不到字元 '{char}' 的資料")
                return
            unicode_hex = format(ord(char), "x").lower()
            stroke_count = 0
            for stroke_index in range(1, 31):
                filename = f"{unicode_hex}_{stroke_index:02d}.svg"
                if os.path.isfile(os.path.join(char_dir, filename)):
                    stroke_count = stroke_index
                else:
                    break
            self.send_json(200, {"char": char, "count": stroke_count})
        except Exception as e:
            self.send_error_json(500, str(e))

    def handle_sheet_csv(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        sheet_id = (params.get("sheet_id") or [""])[0].strip()
        gid = (params.get("gid") or ["0"])[0].strip() or "0"
        if not sheet_id:
            self.send_error_json(400, "缺少 sheet_id")
            return
        headers = {"User-Agent": "Mozilla/5.0 wordbubble"}
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
        urls = [
            f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}",
            f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}",
        ]
        last_err = None
        for url in urls:
            try:
                req = urllib.request.Request(url, headers=headers)
                with opener.open(req, timeout=20) as resp:
                    csv_data = resp.read().decode("utf-8-sig")
                body = csv_data.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            except Exception as e:
                last_err = e
        self.send_error_json(500, f"取得試算表錯誤: {last_err}")

    def handle_moe_stroke(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        ch = (params.get("ch") or [""])[0].strip()
        if not ch:
            self.send_error_json(400, "缺少 ch 參數")
            return
        ch = ch[0]
        cp = ord(ch)
        hex_id = format(cp, "x")
        cache_dir = os.path.join(DIRECTORY, ".cache", "moe_stroke")
        cache_path = os.path.join(cache_dir, f"{hex_id}.json")
        try:
            if os.path.isfile(cache_path):
                with open(cache_path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "public, max-age=604800")
                self.send_header("X-MOE-Cache", "HIT")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            url = f"https://stroke-order.learningweb.moe.edu.tw/dictView.jsp?ID={cp}"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            m = re.search(r'xml\[(\d+)\]="((?:\\.|[^"\\])*)"', html)
            if not m:
                raise RuntimeError("頁面找不到筆順 XML")
            raw = m.group(2)
            xml = (
                raw.replace(r"\"", '"')
                .replace(r"\n", "\n")
                .replace(r"\t", "\t")
                .replace(r"\\/", "/")
            )
            stroke_blocks = re.findall(r"<Stroke>([\s\S]*?)</Stroke>", xml)
            medians = []
            for block in stroke_blocks:
                track = re.search(r"<Track>([\s\S]*?)</Track>", block)
                if not track:
                    medians.append([])
                    continue
                pts = []
                for pm in re.finditer(
                    r'<MoveTo[^>]*\bx="([0-9.]+)"[^>]*\by="([0-9.]+)"',
                    track.group(1),
                ):
                    pts.append([float(pm.group(1)), float(pm.group(2))])
                if not pts:
                    for pm in re.finditer(
                        r'<MoveTo[^>]*\by="([0-9.]+)"[^>]*\bx="([0-9.]+)"',
                        track.group(1),
                    ):
                        pts.append([float(pm.group(2)), float(pm.group(1))])
                medians.append(pts)
            if not medians or not any(medians):
                raise RuntimeError("XML 沒有 Track 軌跡")
            payload = {
                "char": ch,
                "unicode": cp,
                "coordMax": 2048,
                "medians": medians,
                "source": "moe-dictView-track",
            }
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            try:
                os.makedirs(cache_dir, exist_ok=True)
                with open(cache_path, "wb") as f:
                    f.write(body)
            except Exception:
                pass
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "public, max-age=604800")
            self.send_header("X-MOE-Cache", "MISS")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_error_json(502, f"無法取得教育部筆順：「{ch}」 {e}")


def main():
    os.chdir(DIRECTORY)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("", PORT), Handler) as httpd:
        print(f"wordbubble → http://127.0.0.1:{PORT}/")
        print(f"目錄：{DIRECTORY}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")


if __name__ == "__main__":
    main()
