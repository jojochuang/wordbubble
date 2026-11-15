# wordbubble｜生字泡泡

依筆順寫對就消泡泡；支援語詞聽寫、多班級試算表（網址只存本機）。

線上（GitHub Pages）已內建美洲一冊約 **228 字**筆順（`pack-data.js`），學生在家直接開網頁即可練習動畫，**不必再下載離線包**。

課次／考試表用 Google Sheets gviz（JSONP）讀取；本機有 `server.py` 時仍優先走 `/api/sheet_csv`。

## 線上使用

啟用 GitHub Pages（Settings → Pages → Deploy from branch `main` / root）後網址類似：

`https://jojochuang.github.io/wordbubble/`

## 本機啟動

```bash
python3 server.py
```

瀏覽器開啟：<http://127.0.0.1:5002/>

## 主要檔案

| 檔案 | 說明 |
|------|------|
| `index.html` | 生字泡泡主頁 |
| `pack-data.js` | 內建筆順包（約 228 字） |
| `server.py` | 本機 API（選用） |
| `sw.js` | Service Worker |
| `生字泡泡-離線一冊生字.html` | 可另存的完整單檔（選用） |

## 更新筆順包

在有本機 `svg/` 的環境匯出離線包後，把裡面的 `charData` 再匯出成 `pack-data.js`（`window.__BUBBLE_PACK__`）。
