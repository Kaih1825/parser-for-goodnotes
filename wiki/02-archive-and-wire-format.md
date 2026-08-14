[中文](#中文)

<a id="english"></a>

# 02 - ZIP Archive and Protobuf Wire Format Analysis

This chapter introduces the internal ZIP container layout of `.goodnotes` files and how this toolkit directly parses the Protobuf Wire format and Length-Delimited Protobuf Streams without relying on any `.proto` definition files.

---

## 1. ZIP Archive Layout

A `.goodnotes` file is essentially a standard ZIP archive. It can be extracted using standard ZIP extraction tools. A typical ZIP archive structure is as follows:

```
sample.goodnotes/
├── schema.pb                 # File Schema version tag (Field 1 = Varint 35)
├── index.notes.pb            # Notes index file (Page list and notes/<UUID> path mapping)
├── index.attachments.pb      # Attachments index file (Attachment UUID and attachments/<UUID> path mapping)
├── index.events.pb           # Events record file (Dynamic binding of page UUIDs and attachment UUIDs)
├── notes/
│   ├── 31BE4069-02E5-4C5D-...# Protobuf Record stream of a single page (strokes, shapes, text boxes)
│   └── A9F12C3D-8894-4E1B-...
└── attachments/
    ├── 7F129B44-55C1-4D30... # Embedded images (JPEG/PNG) or background PDF files in the note
    └── 31BE4069-02E5-4C5D...
```

### Key Index Members Table

| Member File | Byte/Protobuf Characteristics | Function and Key Fields |
| :--- | :--- | :--- |
| **`schema.pb`** | Contains `0x08 0x23` | **Schema Version Tag**. Protobuf Field 1 (Varint), with a value of `35` (0x23). Represents the data format version of GoodNotes. |
| **`index.notes.pb`** | Consists of multiple Varint length-prefixed Records | **Page Directory**. Contains page UUIDs and `notes/<UUID>` file relative paths. Determines the sequence of note pages. |
| **`index.attachments.pb`** | Varint length-prefixed Record | **Attachment List**. Contains attachment UUIDs and `attachments/<UUID>` relative paths. |
| **`index.events.pb`** | Varint length-prefixed Record | **Page and Attachment Association**. Contains the binding relationship between page UUIDs (`notes/<UUID>`) and attachment UUIDs (`attachments/<UUID>`). |
| **`notes/<UUID>`** | Varint length-prefixed Record Stream | **Single Page Main Data**. Contains all stroke, shape, text, and image attachment references on the page. |

---

## 2. Protobuf Wire Specification

After serialization, Protobuf represents a binary stream arranged continuously in the form of Key-Value pairs. Its basic structure is as follows:

$$\text{Key} = (\text{Field Number} \ll 3) \mid \text{Wire Type}$$

Each Key is a Varint, where its lowest 3 bits (bits 0..2) represent the **Wire Type**, and the higher bits (bits 3+) represent the **Field Number** (Field Tag number).

### Protobuf Supported Wire Types Comparison

| Wire Type (Integer) | Name | Internal Data Structure and Length | Decoding Method (`wire.py`) |
| :---: | :--- | :--- | :--- |
| **0** | `VARINT` | Variable-length integer (1 ~ 10 bytes) | `_read_varint()`: Takes 7 bits each time; MSB 1 indicates more bytes follow. |
| **1** | `FIXED64` | Fixed 8 bytes (64-bit) | `int.from_bytes(8, 'little')` or float64 floating-point number (`<d`). |
| **2** | `LENGTH_DELIMITED` | Varint length $L$ + $L$ bytes Payload | Reads length $L$, then slices $L$ bytes. It could be a string, UTF-8, Sub-Message, or binary (LZ4). |
| **3** | `START_GROUP` | Deprecated | Directly throws `DecodeError` in this toolkit. |
| **4** | `END_GROUP` | Deprecated | Directly throws `DecodeError` in this toolkit. |
| **5** | `FIXED32` | Fixed 4 bytes (32-bit) | `int.from_bytes(4, 'little')` or float32 floating-point number (`<f`). |

---

## 3. Varint Decoding Algorithm

Varint uses Base-128 encoding. The highest bit (MSB, Bit 7) of each byte is the **Continuation Bit**:
- If MSB = `1`: Indicates that the next byte still belongs to the current Varint.
- If MSB = `0`: Indicates that the current byte is the last byte of the Varint.

The remaining lower 7 bits (Bits 0..6) are combined into the final unsigned integer according to Little-Endian format.

The implementation in [`src/goodnotes_re/wire.py`](../src/goodnotes_re/wire.py) is as follows:

```python
def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, 10 * 7, 7): # At most 10 bytes (64-bit int)
        if pos >= len(data):
            raise DecodeError("truncated varint")
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80: # MSB is 0, decoding complete
            return value, pos
    raise DecodeError("varint exceeds 10 bytes")
```

### Varint Decoding Example
If the byte sequence is `0x82 0x01`:
1. First byte `0x82` (`1000 0010`): MSB=1, valid data `000 0010` (value=2), `shift=0`.
2. Second byte `0x01` (`0000 0001`): MSB=0, valid data `000 0001` (value=1), `shift=7` -> $1 \ll 7 = 128$.
3. Final result: $2 + 128 = 130$.

---

## 4. Delimited Message Streams

The `index.notes.pb` and `notes/<UUID>` files within the `.goodnotes` package are not single large Protobuf Messages. Instead, they are composed of multiple **Varint length-prefixed Record streams**:

```
[Record 1 Length (Varint)] [Record 1 Bytes (Protobuf Message)] [Record 2 Length] [Record 2 Bytes] ...
```

For example, if `index.notes.pb` starts with `0x52 0x0a ...`:
- `0x52` = Varint decoded as 82. This indicates that the length of the first Record is 82 bytes.
- The next 82 bytes are read as an independent Protobuf Message.
- Then the next Varint is read to obtain the length of the next Record.

In [`wire.py`](../src/goodnotes_re/wire.py), `decode_delimited_messages()` is responsible for decoding this structure:

```python
def decode_delimited_messages(data: bytes) -> tuple[Message, ...]:
    messages: list[Message] = []
    pos = 0
    while pos < len(data):
        length, pos = _read_varint(data, pos)
        end = pos + length
        if end > len(data):
            raise DecodeError("truncated delimited protobuf record")
        messages.append(decode_message(data[pos:end]))
        pos = end
    return tuple(messages)
```

---

## 5. Schema-Free Recursive Parsing and Unknown Field Retention

To ensure that undefined fields are not lost during parsing, `decode_message()` in [`wire.py`](../src/goodnotes_re/wire.py) adopts schema-free parsing:
1. Sequentially read the Key (`number` and `wire_type`).
2. Read the corresponding length based on `wire_type` (`VARINT` reads Varint, `FIXED32` reads 4 bytes, `FIXED64` reads 8 bytes, `LENGTH_DELIMITED` reads $L$ bytes).
3. Save the original byte slice `raw` and the file offset `offset` into the `Field` dataclass.
4. For `LENGTH_DELIMITED` fields, attempt to call `try_decode_message(value)` for recursive decoding. If successful, treat it as a nested Message; if it fails, retain it as Raw Bytes (which could be UTF-8 strings, RTF text, or Apple LZ4 compressed streams).

```python
@dataclass(frozen=True)
class Field:
    number: int
    wire_type: WireType
    value: int | bytes
    raw: bytes
    offset: int

    def fixed_float(self) -> float | None:
        """Accurately convert to floating-point number only when the tag is FIXED32 or FIXED64, never blindly scan"""
        if self.wire_type is WireType.FIXED32:
            return struct.unpack("<f", struct.pack("<I", self.value))[0]
        if self.wire_type is WireType.FIXED64:
            return struct.unpack("<d", struct.pack("<Q", self.value))[0]
        return None
```

Through this design, the toolkit guarantees **100% lossless parsing and unknown field retention capability**.

---

In the next chapter, **[03 - Apple LZ4 Compression and TPL Memory Image](03-compression-and-tpl-binary.md)**, we will explore in detail the Apple LZ4 stream specifications and the Troy Hanson TPL binary format in the stroke Payload.

---

[English](#english)

<a id="中文"></a>

# 02 - ZIP 容器與 Protobuf Wire 解析 (Archive & Wire Format)

本章節介紹 `.goodnotes` 檔案的 ZIP 內部容器佈局，以及本工具包在不依賴任何 `.proto` 定義檔的情況下，如何直接解析 Protobuf Wire 格式與長度前綴分幀串流（Length-Delimited Protobuf Streams）。

---

## 1. ZIP 容器目錄佈局 (ZIP Archive Layout)

`.goodnotes` 檔案在本質上是一個標準的 ZIP 壓縮包。可以使用標準 ZIP 解壓工具解開。 typical 的 ZIP 包結構如下：

```
sample.goodnotes/
├── schema.pb                 # 檔案 Schema 版本標籤 (Field 1 = Varint 35)
├── index.notes.pb            # 筆記索引檔 (頁面清單與 notes/<UUID> 路徑映射)
├── index.attachments.pb      # 附件索引檔 (附件 UUID 與 attachments/<UUID> 路徑映射)
├── index.events.pb           # 事件紀錄檔 (頁面 UUID 與附件 UUID 的動態綁定)
├── notes/
│   ├── 31BE4069-02E5-4C5D-...# 單一頁面的 Protobuf Record 串流 (筆跡、圖形、文字框)
│   └── A9F12C3D-8894-4E1B-...
└── attachments/
    ├── 7F129B44-55C1-4D30... # 筆記內嵌的圖片 (JPEG/PNG) 或背景 PDF 檔案
    └── 31BE4069-02E5-4C5D...
```

### 關鍵索引成員功能表

| 成員檔案 | 位元組/Protobuf 特徵 | 作用與關鍵欄位 |
| :--- | :--- | :--- |
| **`schema.pb`** | 內含 `0x08 0x23` | **Schema 版本標誌**。Protobuf Field 1 (Varint)，值為 `35` (0x23)。表示 GoodNotes 的資料格式版本。 |
| **`index.notes.pb`** | 由多筆 Varint 長度前綴 Record 組成 | **頁面目錄**。包含頁面 UUID 及 `notes/<UUID>` 檔案相對路徑。決定筆記頁面的先後順序。 |
| **`index.attachments.pb`** | Varint 長度前綴 Record | **附件清單**。包含附件 UUID 與 `attachments/<UUID>` 相對路徑。 |
| **`index.events.pb`** | Varint 長度前綴 Record | **頁面與附件關聯**。包含頁面 UUID (`notes/<UUID>`) 與附件 UUID (`attachments/<UUID>`) 的綁定關係。 |
| **`notes/<UUID>`** | Varint 長度前綴 Record 串流 | **單頁主體數據**。包含該頁面上的所有 stroke (筆跡)、shape (圖形)、text (文字) 與 image attachment 引用。 |

---

## 2. Protobuf Wire 編碼原理 (Protobuf Wire Specification)

Protobuf 序列化後是以 Key-Value 鍵值對形式連續排布的二進制流，其基本結構如下：

$$\text{Key} = (\text{Field Number} \ll 3) \mid \text{Wire Type}$$

每個 Key 是一個 Varint，其低 3 位 (bits 0..2) 為 **Wire Type**，高位 (bits 3+) 為 **Field Number**（欄位 Tag 號碼）。

### Protobuf 支持的 Wire Type 對照

| Wire Type (整數) | 名稱 | 內部資料結構與長度 | 解碼方式 (`wire.py`) |
| :---: | :--- | :--- | :--- |
| **0** | `VARINT` | 可變長度整數 (1 ~ 10 bytes) | `_read_varint()`：每次取 7 bits，MSB 1 表示後續還有 byte。 |
| **1** | `FIXED64` | 固定 8 位元組 (64-bit) | `int.from_bytes(8, 'little')` 或 float64 浮點數 (`<d`)。 |
| **2** | `LENGTH_DELIMITED` | Varint 長度 $L$ + $L$ 位元組 Payload | 讀取長度 $L$，然後切片 $L$ bytes。可能是字串、UTF-8、子 Message 或二進制 (LZ4)。 |
| **3** | `START_GROUP` | 已廢棄 | 本工具包中直接拋出 `DecodeError`。 |
| **4** | `END_GROUP` | 已廢棄 | 本工具包中直接拋出 `DecodeError`。 |
| **5** | `FIXED32` | 固定 4 位元組 (32-bit) | `int.from_bytes(4, 'little')` 或 float32 浮點數 (`<f`)。 |

---

## 3. Varint 7-Bit 解碼演算法 (Varint Decoding Algorithm)

Varint 採用 Base-128 編碼。每個 Byte 的最高位 (MSB, Bit 7) 是 **Continuation Bit**：
- 若 MSB = `1`：表示下一個 Byte 仍屬於當前 Varint。
- 若 MSB = `0`：表示當前 Byte 為該 Varint 的最後一個 Byte。

其餘低 7 位 (Bits 0..6) 按照小端序 (Little-Endian) 組合出最終的無符號整數。

在 [`src/goodnotes_re/wire.py`](../src/goodnotes_re/wire.py) 中的實現如下：

```python
def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, 10 * 7, 7): # 最多 10 個 bytes (64-bit int)
        if pos >= len(data):
            raise DecodeError("truncated varint")
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80: # MSB 為 0，解碼完成
            return value, pos
    raise DecodeError("varint exceeds 10 bytes")
```

### Varint 解碼範例
若位元組序列為 `0x82 0x01`：
1. 第一位元組 `0x82` (`1000 0010`): MSB=1，有效資料 `000 0010` (值=2)，`shift=0`。
2. 第二位元組 `0x01` (`0000 0001`): MSB=0，有效資料 `000 0001` (值=1)，`shift=7` -> $1 \ll 7 = 128$。
3. 最終結果：$2 + 128 = 130$。

---

## 4. Length-Delimited 串流分幀 (Delimited Message Streams)

`.goodnotes` 包內的 `index.notes.pb` 與 `notes/<UUID>` 檔案並非單一的大 Protobuf Message，而是由多個 **Varint 長度前綴包裹的 Record 串流** 組成：

```
[Record 1 Length (Varint)] [Record 1 Bytes (Protobuf Message)] [Record 2 Length] [Record 2 Bytes] ...
```

例如：若 `index.notes.pb` 開頭為 `0x52 0x0a ...`：
- `0x52` = Varint 解碼為 82。表示第一筆 Record 長度為 82 位元組。
- 接續讀取 82 位元組作為獨立的 Protobuf Message。
- 再讀取下一個 Varint 獲取下一筆 Record 長度。

在 [`wire.py`](../src/goodnotes_re/wire.py) 中，`decode_delimited_messages()` 負責解開此結構：

```python
def decode_delimited_messages(data: bytes) -> tuple[Message, ...]:
    messages: list[Message] = []
    pos = 0
    while pos < len(data):
        length, pos = _read_varint(data, pos)
        end = pos + length
        if end > len(data):
            raise DecodeError("truncated delimited protobuf record")
        messages.append(decode_message(data[pos:end]))
        pos = end
    return tuple(messages)
```

---

## 5. 無模式 (Schema-Free) 遞迴解析與未知欄位保留

為確保解析時不會丟失未定義的欄位，[`wire.py`](../src/goodnotes_re/wire.py) 中的 `decode_message()` 採用無模式解析：
1. 依序讀取 Key (`number` 與 `wire_type`)。
2. 根據 `wire_type` 讀取對應長度（`VARINT` 讀取 Varint，`FIXED32` 讀 4 bytes，`FIXED64` 讀 8 bytes，`LENGTH_DELIMITED` 讀 $L$ bytes）。
3. 保存原始位元組切片 `raw` 與檔案偏移量 `offset` 到 `Field` dataclass。
4. 對於 `LENGTH_DELIMITED` 欄位，嘗試調用 `try_decode_message(value)` 進行遞迴解碼。若成功則將其視為嵌套 Message，若失敗則保留為 Raw Bytes（可能是 UTF-8 字串、RTF 文本或 Apple LZ4 壓縮串流）。

```python
@dataclass(frozen=True)
class Field:
    number: int
    wire_type: WireType
    value: int | bytes
    raw: bytes
    offset: int

    def fixed_float(self) -> float | None:
        """僅在標籤為 FIXED32 或 FIXED64 時精準轉為浮點數，絕不盲目掃描"""
        if self.wire_type is WireType.FIXED32:
            return struct.unpack("<f", struct.pack("<I", self.value))[0]
        if self.wire_type is WireType.FIXED64:
            return struct.unpack("<d", struct.pack("<Q", self.value))[0]
        return None
```

透過這種設計，工具包保證了 **100% 的無損解析與未知欄位保留能力**。

---

在下一章 **[03 - Apple LZ4 壓縮與 TPL 記憶體映像](03-compression-and-tpl-binary.md)** 中，我們將詳細探討筆跡 Payload 中的 Apple LZ4 串流規格以及 Troy Hanson TPL 二進位格式。
