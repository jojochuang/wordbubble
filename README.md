# wordbubble｜生字泡泡

依筆順寫對就消泡泡；支援語詞聽寫、多班級試算表（網址只存本機）。

## 本機啟動

```bash
python3 server.py
```

瀏覽器開啟：<http://127.0.0.1:5002/>

## 本機筆順資料（選用）

完整手寫練習需要本機 `svg/`（各字資料夾）。此 repo 不含大型字形檔，請自行放到專案根目錄：

```text
wordbubble/
  svg/
    山/
      ….svg
      medians.json   # 可選
```

沒有 `svg/` 時，仍可載入試算表；筆順方向可走教育部 Track API（需網路）。

## 主要檔案

| 檔案 | 說明 |
|------|------|
| `index.html` | 生字泡泡主頁 |
| `server.py` | 靜態服務 + `/api/sheet_csv`、`/api/moe_stroke`、`/api/get_stroke_count` |
| `sw.js` | Service Worker |
| `char_bubble.webmanifest` | PWA 清單 |

## 離線

設定裡可「匯出全年離線包」成單一 HTML，方便 AirDrop 到 iPad。
