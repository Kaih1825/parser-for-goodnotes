# 03 - Apple LZ4 壓縮與 TPL 記憶體映像 (Compression & TPL Binary)

本章節深入分析 GoodNotes 儲存筆跡（Ink Stroke）的核心二進位技術：Apple Framed LZ4 壓縮格式 (`bv41`/`bv4$`)、Troy Hanson TPL 記憶體映像 (`tpl\0`) 結構，以及在 `bv4$` 魔術標記之後緊跟的 Protobuf Trailer（筆跡 RGBA 顏色與 Lasso 移動向量）。

---

## 1. Apple Framed LZ4 壓縮格式 (`bv41` / `bv4$`)

在 Protobuf Record 欄位中，凡是代表筆跡數據的位元組切片，均包覆在 Apple 專有的 Framed LZ4 壓縮串流中。該串流由一個或多個區塊 (Block) 連接而成，並以特定 4 位元組 Magic Marker 標記。

### Apple LZ4 區塊結構對照

```
+-------------------+----------------------+-------------------+--------------------------+
| Block Magic (4B)  | Header (8 Bytes)     | Compressed Data   | Terminator / Next Block  |
+-------------------+----------------------+-------------------+--------------------------+
| "bv41" or "bv4-"  | UncompressedSize (4B)| Block Payload     | ...                      |
|                   | StoredSize (4B)      | (Length = Stored) | "bv4$" (Stream End)      |
+-------------------+----------------------+-------------------+--------------------------+
```

| 4-Byte Magic | 區塊類型 | 說明 |
| :---: | :--- | :--- |
| **`bv41`** | Compressed Block | 使用標準 LZ4 演算法壓縮的資料塊。表頭包含小端序 uint32 `UncompressedSize` 與 `StoredSize`。 |
| **`bv4-`** | Stored Block | 未經壓縮的原始區塊（`StoredSize == UncompressedSize`）。 |
| **`bv4$`** | Stream End Marker | **串流結束標籤**。當讀取到 `bv4$` 時，表示 LZ4 解壓縮完成。**注意：`bv4$` 之後剩餘的位元組為 Protobuf Trailer。** |

---

## 2. Pure-Python LZ4 解壓縮演算法 (`compression.py`)

為了保持零外部 C 程式庫依賴，[`src/goodnotes_re/compression.py`](file:///Users/kai/Documents/Goodnotes/src/goodnotes_re/compression.py) 實現了完整的 LZ4 解壓器。解壓時維護 64KB (65,536 Bytes) 的歷史滑動視窗 (History Window)：

### LZ4 Token 解碼邏輯

LZ4 的位元組流由一系列 Token 組成：
- **Token Byte**：高 4 位 (`token >> 4`) 為 **Literal Length**；低 4 位 (`token & 15`) 為 **Match Length**。
- **Literal Value**：若高 4 位等於 15，則接續讀取位元組直到 Byte $\neq 255$ 加總長度。讀取對應長度的字面量 byte 直接寫入 output。
- **Match Offset**：小端序 2 位元組 uint16，表示向歷史視窗回溯的距離。Offset 絕不能為 0。
- **Match Length**：若低 4 位等於 15，接續讀取擴充長度，最後固定加上偏移量 $+4$。從 `(history + output)[-offset]` 重複拷貝對應位元組。

```python
def decode_apple_lz4(data: bytes) -> tuple[bytes, int]:
    output = bytearray()
    position = 0
    while True:
        if position + 4 > len(data):
            raise CompressionError("missing Apple LZ4 end marker")
        magic = data[position : position + 4]
        position += 4
        if magic == b"bv4$":
            return bytes(output), position # 回傳 (解壓後數據, 消耗的位元組數)
        if magic not in (b"bv41", b"bv4-"):
            raise CompressionError(f"unexpected Apple LZ4 block magic {magic!r}")
        
        uncompressed_size, stored_size = struct.unpack_from("<II", data, position)
        position += 8
        block = data[position : position + stored_size]
        position += stored_size
        
        if magic == b"bv4-":
            output.extend(block)
        else:
            output.extend(_decode_lz4_block(block, uncompressed_size, bytes(output)))
```

---

## 3. Troy Hanson TPL 記憶體映像格式 (`tpl\0`)

當 Apple LZ4 解壓後，得到的原始位元組串流必然以 `tpl\0` 魔術標記開頭。這是基於 C 語言高效率 serialization 庫 [Troy Hanson TPL (tpl.sourceforge.net)](https://troydhanson.github.io/tpl/) 的記憶體映像。

### TPL Binary Header 結構 (9 Bytes + Format String)

```
0   1   2   3   4           7   8                                  N   N+1
+---+---+---+---+---------------+----------------------------------+---+------------------------+
| 't' 'p' 'l'|F | ImageSize (4B)| Format String (ASCII, Null-term) |00 | Binary Packed Values   |
+---+---+---+---+---------------+----------------------------------+---+------------------------+
```

| 欄位名稱 | 偏移與長度 | 說明與檢驗規約 |
| :--- | :--- | :--- |
| **Magic** | Offset 0..2 (3B) | 必須固定為 ASCII 碼 `tpl` (`0x74 0x70 0x6c`)。 |
| **Flags** | Offset 3 (1B) | 位元標誌。Bit 0 (`flags & 1`) 若為 1 表示 Big-Endian (本專案不支援)；GoodNotes 固定為 0 (Little-Endian)。 |
| **ImageSize** | Offset 4..7 (4B) | 小端序 uint32，表示整個 TPL 映像檔的位元組總長度。必須等於 `len(data)`。 |
| **Format String** | Offset 8..end | 以 `\0` (0x00) 結尾的 ASCII 描述符字串。定義了後續二進制數據的巢狀結構類型！ |

---

## 4. TPL Format String 語法與點陣型別解析

在 [`src/goodnotes_re/tpl.py`](file:///Users/kai/Documents/Goodnotes/src/goodnotes_re/tpl.py) 中，`decode_tpl()` 會先解析 Format String，構建出語法樹 (Format Tree)，再根據結構讀取二進制數據。

### TPL Format 字元對照表

| 字元標記 | 對應 C/二進位型別 | 長度 (Bytes) | Python 讀取解碼方式 (`struct.unpack`) |
| :---: | :--- | :---: | :--- |
| `c` | char / int8 | 1 | `<b` |
| `j` / `v` | short / uint16 | 2 | `<h` / `<H` |
| `i` / `u` | int / uint32 | 4 | `<i` / `<I` (uint32 常轉為 IEEE 754 float32) |
| `I` / `U` | int64 / uint64 | 8 | `<q` / `<Q` |
| `f` | double (float64) | 8 | `<d` |
| `s` | string | uint32 len + bytes | 先讀 uint32 長度，再讀取對應長度 UTF-8 字串 |
| `A(...)` | Dynamic Array | Variable | 先讀 uint32 元素個數 $N$，再循環 $N$ 次解碼內嵌元素 |
| `S(...)` | Structure / Tuple | Variable | 解碼一組固定順序的元素元組 |

### GoodNotes 筆跡常用 TPL Format 描述符

 GoodNotes 在不同版本與筆尖工具（鋼筆、圓珠筆、畫筆、螢光筆）下使用不同的 TPL 描述符：

1. **`vuA(v)A(S(uu))A(S(uuuu))vA(f)` (經典 4 元組筆跡)**：
   - `values[2]` (`A(v)`): 抬筆/落筆標誌陣列 (0 表示抬筆分組, 1 表示落筆續畫)。
   - `values[3]` (`A(S(uu))`): 起始點座標 $(x_0, y_0)$ (固定 32-bit uint32，經 IEEE 754 轉為 float32)。
   - `values[4]` (`A(S(uuuu))`): 4 元組段陣列 $(x_1, y_1, x_2, y_2)$，表示連續二進制線段。

2. **`vuA(v)A(S(uuuuu))A(S(uuuuuuuuuuu))` (11 元組高精度筆跡)**：
   - 含有 5 元組點陣 $(x, y, -, -, p)$ 與 11 元組詳細點陣 (包含壓感 $p_1, p_2$)。

3. **高密度動態壓感格式 (6-float / 3-float / 5-float 陣列)**：
   - 6 元組：$(x_1, y_1, x_2, y_2, p_1, p_2)$ - 每段兩點與各自壓感。
   - 3 元組：$(x, y, p)$ - 控制點座標與動態壓感。
   - 5 元組：$(x, y, p, w, \text{angle})$ - 畫筆向量點陣。

---

## 5. `bv4$` 後方 Protobuf Trailer 解析 (RGBA 顏色與 Lasso 移動)

當 `decode_apple_lz4()` 在 `position` 處讀到 `bv4$` 結尾標記時，`field_data[position:]` 剩餘的位元組**並非廢棄數據**，而是標準的 Protobuf Message (稱為 Trailer)。

在 [`src/goodnotes_re/stroke.py`](file:///Users/kai/Documents/Goodnotes/src/goodnotes_re/stroke.py) 中，透過解碼 Trailer 提取出筆跡的真實顏色與移動矩陣：

```
[Apple LZ4 Stream ("bv41" ... "bv4$")] [Protobuf Trailer Bytes]
                                       ├── Field 4 (Length-delimited): RGBA Color
                                       │   ├── Tag 1 (FIXED32): Red (0.0 ~ 1.0)
                                       │   ├── Tag 2 (FIXED32): Green (0.0 ~ 1.0)
                                       │   ├── Tag 3 (FIXED32): Blue (0.0 ~ 1.0)
                                       │   └── Tag 4 (FIXED32): Alpha (0.0 ~ 1.0)
                                       └── Field 6 (Length-delimited): Lasso Move Offset
                                           ├── Tag 1 (FIXED32): dx (X 軸平移像素)
                                           └── Tag 2 (FIXED32): dy (Y 軸平移像素)
```

### RGBA 顏色提取 (`extract_color_from_trailer`)

```python
def extract_color_from_trailer(trailer_bytes: bytes) -> tuple[str, float]:
    msg = decode_message(trailer_bytes)
    for field in msg.fields:
        if field.number == 4 and isinstance(field.value, bytes):
            color_msg = decode_message(field.value)
            r_val = color_msg.by_number(1)[0].fixed_float() or 0.0
            g_val = color_msg.by_number(2)[0].fixed_float() or 0.0
            b_val = color_msg.by_number(3)[0].fixed_float() or 0.0
            a_val = color_msg.by_number(4)[0].fixed_float() if color_msg.by_number(4) else 1.0
            
            r_int = min(255, max(0, int(round(r_val * 255.0))))
            g_int = min(255, max(0, int(round(g_val * 255.0))))
            b_int = min(255, max(0, int(round(b_val * 255.0))))
            return f"#{r_int:02x}{g_int:02x}{b_int:02x}", a_val
    return "#000000", 1.0
```

> **螢光筆 (Highlighter) 自動判定**：若提取出的 `alpha < 0.95`（如透明度 0.5），則該筆跡自動判定為螢光筆，在 SVG 繪製時會保持 Alpha 半透明重疊效果。

### 套索 (Lasso) 工具移動偏移量提取 (`extract_move_offset_from_trailer`)

當使用者在 GoodNotes 中使用套索工具圈選筆跡並拖移到新位置時，GoodNotes **完全不會修改 TPL 內的二進制原始點座標**，而是將位移向量 $(dx, dy)$ 追加寫入 Trailer 的 **Field 6**。

解碼器讀取 Field 6 中的兩個 FIXED32 浮點數得到 $(dx, dy)$，並將其加算至 TPL 提取出的每個點 $(x + dx, y + dy)$ 上，從而還原出筆跡在頁面上的真實顯示位置。

---

在下一章 **[04 - 筆跡幾何與向量 Ribbon 重建](file:///Users/kai/Documents/Goodnotes/wiki/04-stroke-geometry-and-rendering.md)** 中，我們將詳細介紹法向量計算、向量 Ribbon 繪製以及 v9 橡皮擦切口凸包演算法。
