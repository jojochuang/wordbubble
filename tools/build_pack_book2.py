#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build pack-data-book2.js from sheet B2–D37 + local svg/ (+ moe cache/fetch)."""

from __future__ import print_function

import csv
import io
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path("/Users/jiawu/Documents/word writing")
SVG_ROOT = ROOT / "svg"
MOE_CACHE = ROOT / ".cache" / "moe_stroke"
OUT = Path("/Users/jiawu/Documents/GitHub/wordbubble/pack-data-book2.js")
SVG_VIEW = 540
MOE_COORD = 2048
SHEET_ID = "1MxROi0vIZ2Dk1doq3jJWlP28_t2R7j7q8N4h1YCs8Qc"
GID = "1601198504"


def log(*a):
    print(*a, flush=True)


def fetch_chars():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    chars, seen = [], set()
    for i in range(1, min(37, len(rows))):  # rows 2–37
        r = rows[i]
        for c in range(1, 4):  # B–D
            cell = r[c] if c < len(r) else ""
            for ch in cell:
                if ("\u4e00" <= ch <= "\u9fff") or ("\u3400" <= ch <= "\u4dbf"):
                    if ch not in seen:
                        seen.add(ch)
                        chars.append(ch)
    return chars


def normalize_d(d):
    d = (d or "").replace(",", " ")
    return re.sub(r"\s+", " ", d).strip()


def parse_path_d(svg_text):
    svg_text = re.sub(r'\sxmlns(:\w+)?="[^"]*"', "", svg_text)
    root = ET.fromstring(svg_text)
    parts = []
    for p in root.iter():
        if p.tag.endswith("path"):
            d = (p.get("d") or "").strip()
            if d:
                parts.append(d)
    return normalize_d(" ".join(parts))


def strip_trailing_z(d):
    d = normalize_d(d)
    if d.endswith("Z") or d.endswith("z"):
        return d[:-1].strip()
    return d


def diff_cumulative(ds):
    out, prev = [], ""
    for cur in ds:
        cur = normalize_d(cur)
        if not prev:
            out.append(cur)
        elif cur.startswith(prev):
            out.append(cur[len(prev) :].strip())
        else:
            prev_open = strip_trailing_z(prev)
            if prev_open and cur.startswith(prev_open):
                out.append(cur[len(prev_open) :].strip())
            else:
                out.append(cur)
        prev = cur
    return [d for d in out if d and len(d) > 4]


def pick_largest_subpath(d):
    t = normalize_d(d)
    if not t:
        return t
    chunks = [c.strip() for c in re.split(r"\s+(?=M\s)", t, flags=re.I) if c.strip()]
    if len(chunks) <= 1:
        return t
    return max(chunks, key=len)


def load_strokes(ch):
    hexid = format(ord(ch), "x").lower()
    folder = SVG_ROOT / ch
    if not folder.is_dir():
        raise FileNotFoundError(ch)
    texts = []
    for i in range(1, 31):
        fp = folder / f"{hexid}_{i:02d}.svg"
        if not fp.is_file():
            break
        texts.append(fp.read_text(encoding="utf-8", errors="replace"))
    if not texts:
        raise FileNotFoundError(f"no svg for {ch}")
    cum = [c for c in (parse_path_d(t) for t in texts) if c]
    strokes = [pick_largest_subpath(d) for d in diff_cumulative(cum)]
    if not strokes:
        raise RuntimeError(f"empty strokes {ch}")
    return strokes


def scale_medians(raw, stroke_count, coord_max):
    if not isinstance(raw, list) or len(raw) != stroke_count:
        return None
    scale = SVG_VIEW / float(coord_max or SVG_VIEW)
    out = []
    for pts in raw:
        if not isinstance(pts, list) or len(pts) < 2:
            return None
        line = []
        for p in pts:
            if not isinstance(p, (list, tuple)) or len(p) < 2:
                return None
            line.append({"x": float(p[0]) * scale, "y": float(p[1]) * scale})
        out.append(line)
    return out


def load_medians_local(ch, stroke_count):
    mj = SVG_ROOT / ch / "medians.json"
    if mj.is_file():
        try:
            j = json.loads(mj.read_text(encoding="utf-8"))
            vb = j.get("viewBox")
            coord = vb[2] if isinstance(vb, list) and len(vb) >= 3 else SVG_VIEW
            m = scale_medians(j.get("medians"), stroke_count, coord)
            if m:
                return m, "local-svg+jpg-median"
        except Exception:
            pass
    cache = MOE_CACHE / f"{format(ord(ch), 'x')}.json"
    if cache.is_file():
        try:
            j = json.loads(cache.read_text(encoding="utf-8"))
            m = scale_medians(j.get("medians"), stroke_count, j.get("coordMax") or MOE_COORD)
            if m:
                return m, "local-svg+moe-track"
        except Exception:
            pass
    return None, None


def fetch_moe_medians(ch, stroke_count):
    url = f"https://stroke-order.learningweb.moe.edu.tw/dictView.jsp?ID={ord(ch)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", "replace")
    m = re.search(r'xml\[(\d+)\]="((?:\\.|[^"\\])*)"', html)
    if not m:
        return None, None
    raw = m.group(2)
    xml = (
        raw.replace(r"\"", '"')
        .replace(r"\n", "\n")
        .replace(r"\t", "\t")
        .replace(r"\\/", "/")
    )
    blocks = re.findall(r"<Stroke>([\s\S]*?)</Stroke>", xml)
    medians = []
    for block in blocks:
        track = re.search(r"<Track>([\s\S]*?)</Track>", block)
        if not track:
            medians.append([])
            continue
        pts = []
        for pm in re.finditer(
            r'<MoveTo[^>]*\bx="([0-9.]+)"[^>]*\by="([0-9.]+)"', track.group(1)
        ):
            pts.append([float(pm.group(1)), float(pm.group(2))])
        if not pts:
            for pm in re.finditer(
                r'<MoveTo[^>]*\by="([0-9.]+)"[^>]*\bx="([0-9.]+)"', track.group(1)
            ):
                pts.append([float(pm.group(2)), float(pm.group(1))])
        medians.append(pts)
    scaled = scale_medians(medians, stroke_count, MOE_COORD)
    if scaled:
        MOE_CACHE.mkdir(parents=True, exist_ok=True)
        payload = {
            "char": ch,
            "unicode": ord(ch),
            "coordMax": MOE_COORD,
            "medians": medians,
            "source": "moe-dictView-track",
        }
        (MOE_CACHE / f"{format(ord(ch), 'x')}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        return scaled, "local-svg+moe-track"
    return None, None


def main():
    chars = fetch_chars()
    log("chars", len(chars))
    char_data = {}
    fail = []
    need_moe = []

    for i, ch in enumerate(chars):
        try:
            strokes = load_strokes(ch)
            medians, source = load_medians_local(ch, len(strokes))
            if not medians:
                need_moe.append((ch, len(strokes)))
                char_data[ch] = {"strokes": strokes, "medians": None, "source": "local-svg"}
            else:
                char_data[ch] = {"strokes": strokes, "medians": medians, "source": source}
        except Exception as e:
            fail.append((ch, str(e)))
        if (i + 1) % 50 == 0:
            log("strokes", i + 1, "/", len(chars))

    log("need moe fetch", len(need_moe), "fail strokes", fail)

    def one(item):
        ch, n = item
        try:
            return ch, fetch_moe_medians(ch, n)
        except Exception as e:
            return ch, (None, None)

    done = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(one, it) for it in need_moe]
        for fut in as_completed(futs):
            ch, (medians, source) = fut.result()
            done += 1
            if medians:
                char_data[ch]["medians"] = medians
                char_data[ch]["source"] = source
            if done % 20 == 0 or done == len(need_moe):
                log("moe", done, "/", len(need_moe))

    no_med = [ch for ch, rec in char_data.items() if not rec.get("medians")]
    log("ok", len(char_data), "no_med", len(no_med), "".join(no_med))

    pack = {
        "charData": char_data,
        "label": "美洲二冊筆順包",
        "charCount": len(char_data),
        "sheetGid": GID,
        "range": "B2:D37",
    }
    OUT.write_text(
        f"/* 美洲二冊 {len(char_data)} 字筆順（B2–D37） */\n"
        "window.__BUBBLE_PACK_BOOK2__="
        + json.dumps(pack, ensure_ascii=False).replace("<", "\\u003c")
        + ";\n",
        encoding="utf-8",
    )
    log("wrote", OUT, "MB", round(OUT.stat().st_size / 1024 / 1024, 2))
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
