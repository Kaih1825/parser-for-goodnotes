<a id="english"></a>

# 04 - Stroke Geometry & Rendering
[中文](#中文)

This chapter details how to mathematically reconstruct control points and pressure data into smooth, variable-width vector SVG Path Ribbons, as well as how to handle strokes partially cut by the eraser (`v9` Native Mesh).

---

## 1. Stroke Point & Pressure Model

Each stroke consists of a series of control points with pressure values. It is defined as `StrokePoint`:

```python
@dataclass(frozen=True)
class StrokePoint:
    x: float
    y: float
    pressure: float = 1.0  # Radius or relative pressure ratio
```

If the point array does not contain explicit pressure (e.g., pure 2D coordinates), half of the `default_width` (i.e., default radius $r = \text{width} / 2.0$) is used as the base pressure.

---

## 2. Variable-Width Ribbon Algorithm

Drawing polylines directly using SVG `stroke-width` cannot represent the variable thickness effect of a real stylus (such as a fountain pen or calligraphy pen) responding to pressure and speed. The process employs the **Bi-lateral Offset Outlines** algorithm based on normal vectors to generate closed 2D vector polygon Ribbons.

### Normal Vector Calculation and Smoothing in 3 Steps

For a stroke sequence of $N$ points $P_0, P_1, \dots, P_{N-1}$ (point $P_i = (x_i, y_i, r_i)$):

#### Step 1: Tangent Vector and Normal Vector Calculation
For each point $P_i$, calculate the tangent vector $\vec{T}_i = (\Delta x_i, \Delta y_i)$:
- Endpoint $i=0$: $\vec{T}_0 = P_1 - P_0$
- Endpoint $i=N-1$: $\vec{T}_{N-1} = P_{N-1} - P_{N-2}$
- Middle points $1 \le i \le N-2$: Use central difference $\vec{T}_i = P_{i+1} - P_{i-1}$

Rotate the tangent vector 90 degrees to get the original normal vector $\vec{N}_i = (-T_{y}, T_{x})$. If $\|\vec{N}_i\| < 10^{-6}$, it defaults to $(0.0, 1.0)$.

#### Step 2: Sliding Average Smoothing
To prevent minor stroke jitters from causing jagged intersections between the two side outlines, a neighborhood sliding average is applied to the normal vectors:

$$\vec{S}_i = \frac{1}{3} \left( \vec{N}_{i-1} + \vec{N}_i + \vec{N}_{i+1} \right)$$

#### Step 3: Re-normalization **[Critical Fix]**
Direct averaging shortens the length of the normal vector (making the stroke thinner at turns). It must be re-normalized to a unit vector:

$$\hat{n}_i = \frac{\vec{S}_i}{\|\vec{S}_i\|}$$

#### Step 4: Generate Left / Right Outlines
Based on the dynamic radius $r_i$ of point $P_i$, offset it along the normal vector directions on both sides:

$$L_i = P_i + r_i \cdot \hat{n}_i, \quad R_i = P_i - r_i \cdot \hat{n}_i$$

---

## 3. SVG Smooth Path and Rounded Cap Construction

After obtaining the $L_i$ and $R_i$ point sets, `build_stroke_ribbon()` uses SVG drawing commands to assemble a closed path:

```
[Start Cap (Arc A)] ──► [Right Side Smooth Quad Curves (Q)] ──► [End Cap (Arc A)] ──► [Left Side Smooth Quad Curves (Q)] ──► Close (Z)
```

```python
# Rounded cap and smooth control commands (key snippet from build_stroke_ribbon)
d = [f"M {left_side[0][0]:.2f} {left_side[0][1]:.2f}"]
# 1. Start rounded cap Arc (A)
d.append(f"A {r0:.2f} {r0:.2f} 0 0 1 {right_side[0][0]:.2f} {right_side[0][1]:.2f}")
# 2. Right side smooth Quadratic Bezier (Q)
d.extend(smooth_commands(right_side))
# 3. End rounded cap Arc (A)
d.append(f"A {r1:.2f} {r1:.2f} 0 0 1 {left_side[-1][0]:.2f} {left_side[-1][1]:.2f}")
# 4. Left side reversed smooth Quadratic Bezier (Q)
d.extend(smooth_commands(reversed_left))
d.append("Z")
```

---

## 4. Eraser Cut & Clipped Strokes (`native_cgpaths` Vector Architecture)

When a user uses the eraser to slice or cut through strokes, or draws precise fountain pen ink, GoodNotes performs a boolean path clip and writes out exact closed vector contour panels (`native_cgpaths`) directly into the LZ4-compressed TPL binary container.

### 1. Dual TPL Schema Shift Architecture

GoodNotes 6 employs two primary TPL schema variations for storing native vector CGPath instructions:

| Schema Attribute | Variation A (`vuA(v)...`, e.g., with width `u`) | Variation B (`vA(v)...`, e.g., without width `u`) |
| :--- | :--- | :--- |
| **Shift Offset** | `shift = 1` (12 values total) | `shift = 0` (11 values total) |
| **Command Counts per Panel** | `values[5]` | `values[4]` |
| **Command Codes** | `values[6]` (`{2, 4, 5}`) | `values[5]` (`{0, 2, 3}`) |
| **Start Points `(x0, y0)`** | `values[7]` | `values[6]` |
| **Cubic Bezier Curves `(c1, c2, p2)`** | `values[9]` | `values[8]` |
| **Arc Parameters `(cx, cy, r, a0, a1)`** | `values[10]` | `values[9]` |
| **Arc Clockwise Flags `(0 / 1)`** | `values[11]` | `values[10]` |

### 2. Apple CoreGraphics Command Mapping

The command codes map to standard Apple `CGPath` operations:
- **`MoveTo` (`CMD 2` in Var A / `CMD 0` in Var B)**: Moves pen to starting coordinate `(x0, y0)` from start-point pool.
- **`CubicTo` (`CMD 4` in Var A / `CMD 2` in Var B)**: Cubic Bezier curve using 3 coordinate pairs `(c1x, c1y, c2x, c2y, p2x, p2y)` from cubic pool.
- **`ArcTo` (`CMD 5` in Var A / `CMD 3` in Var B)**: Circular arc `(cx, cy, r, a0, a1, flag)` matching `CGPathAddArc`.

### 3. Apple `CGPathAddArc` to SVG `A` Conversion

In screen coordinates ($Y$-down), an arc is converted to SVG path command `A rx ry 0 large_arc sweep end_x end_y`:
- Start point: $(cx + r\cos(a_0), cy + r\sin(a_0))$, which matches the preceding Bezier end point with 0.0000 delta.
- End point: $(cx + r\cos(a_1), cy + r\sin(a_1))$.
- Sweep & Large Arc:
  $$\Delta\theta = (a_0 - a_1) \pmod{2\pi}$$
  $$\text{sweep} = 0 \text{ if } \text{flag} == 1 \text{ else } 1, \quad \text{large\_arc} = 1 \text{ if } \Delta\theta > \pi \text{ else } 0$$

### 4. Nonzero Winding & Subpixel Seam Bridging

- **Nonzero Winding Rule**: The stroke is composed of contiguous, slightly overlapping quad panels. Under SVG default `fill-rule="nonzero"`, all panels seamlessly blend together into a 100% solid stroke without internal parity holes.
- **Subpixel Antialiasing Seam Bridging**: To prevent subpixel antialiasing hairline cracks between adjacent panels during browser/PDF rendering, a hairline stroke (`stroke="{s_color}" stroke-width="{0.4 * dpi_scale}" stroke-linejoin="round"`) is applied matching the fill color.

### 5. Lasso Move Transformation (`dx, dy`)

When strokes are moved using the Lasso tool, relative offsets $(dx, dy)$ extracted from the Protobuf trailer are automatically propagated to all control points, cubic curve points, and arc centers in `native_cgpaths`.

---

## 5. Jitter Filtering and Safe Split Guard (Jitter & Split Safety)

### 1. Jitter Ratio (`_path_jitter_ratio`)
Sometimes certain arrays happen to fit within the coordinate value range, but they are actually directional/tangent metadata of the stroke rather than path points.
The process calculates the directional reversal rate of adjacent vectors:

$$\text{Jitter Ratio} = \frac{\text{Number of direction reversals (Cos angle } < -0.3\text{)}}{\text{Total number of vector segments}}$$

The Jitter Ratio of a normal stroke is usually less than `0.25`. If it exceeds the threshold `_JITTER_REJECT_THRESHOLD = 0.35`, it is determined to be a metadata array and filtered out.

### 2. Distance Split Guard (`split_stroke_points`)
When the distance between two adjacent control points exceeds the safety threshold of `300.0` points, it indicates a point jump or an unrecorded pen lift at that location. `split_stroke_points()` safely cuts it into independent sub-strokes to avoid drawing erroneous straight lines across the entire page.

---

In the next chapter **[05 - Shapes, Text, and Elements](05-shapes-text-and-elements#english)**, we will introduce parsing details for vector shapes, arrow markers, rich text boxes, and image crops.

---

<a id="中文"></a>

# 04 - 筆跡幾何與向量 Ribbon 重建 (Stroke Geometry & Rendering)
[English](#english)

本章節詳細說明如何將提取出的控制點與壓感資料，數學化重建為平滑、具備自然寬度變化的向量 SVG Path Ribbon（帶狀路徑），以及處理被橡皮擦局部擦除切開的筆跡（`v9` Native Mesh）。

---

## 1. 筆跡點與壓感模型 (Stroke Point & Pressure Model)

每一條筆跡由一系列帶有壓感值的控制點組成。定義為 `StrokePoint`：

```python
@dataclass(frozen=True)
class StrokePoint:
    x: float
    y: float
    pressure: float = 1.0  # 半徑或相對壓感比例
```

若點陣中未包含顯式壓感（如單純 2D 座標），則使用提取的 `default_width` 的一半（即預設半徑 $r = \text{width} / 2.0$）作為基礎壓感。

---

## 2. 變寬 Ribbon 法向量演算法 (Variable-Width Ribbon Algorithm)

直接使用 SVG `stroke-width` 繪製折線無法呈現真實手寫筆尖（如鋼筆、書法筆）隨壓感與速度變化的粗細效果。我們採用 **法向量偏移雙側輪廓 (Bi-lateral Offset Outlines)** 演算法，產生封閉的 2D 向量多邊形 Ribbon。

### 法向量計算與平滑三步驟

對包含 $N$ 個點的筆跡序列 $P_0, P_1, \dots, P_{N-1}$（點 $P_i = (x_i, y_i, r_i)$）：

#### 步驟 1：切線向量與法向量計算
對每個點 $P_i$，計算切線向量 $\vec{T}_i = (\Delta x_i, \Delta y_i)$：
- 端點 $i=0$：$\vec{T}_0 = P_1 - P_0$
- 端點 $i=N-1$：$\vec{T}_{N-1} = P_{N-1} - P_{N-2}$
- 中間點 $1 \le i \le N-2$：採用中心差分 $\vec{T}_i = P_{i+1} - P_{i-1}$

將切線向量旋轉 90 度得到原始法向量 $\vec{N}_i = (-T_{y}, T_{x})$。若 $\|\vec{N}_i\| < 10^{-6}$，則預設為 $(0.0, 1.0)$。

#### 步驟 2：法向量滑動平均平滑 (Sliding Average Smoothing)
為防止筆劃微小抖動導致兩側輪廓產生鋸齒交叉，對法向量進行鄰域滑動平均：

$$\vec{S}_i = \frac{1}{3} \left( \vec{N}_{i-1} + \vec{N}_i + \vec{N}_{i+1} \right)$$

#### 步驟 3：長度重新歸一化 (Re-normalization) **[關鍵修正]**
直接平均會縮短法向量長度（使轉彎處筆劃變細）。必須重新歸一化為單位向量：

$$\hat{n}_i = \frac{\vec{S}_i}{\|\vec{S}_i\|}$$

#### 步驟 4：產生左右側點集 (Left / Right Outlines)
根據點 $P_i$ 的動態半徑 $r_i$，向兩側法向量方向偏移：

$$L_i = P_i + r_i \cdot \hat{n}_i, \quad R_i = P_i - r_i \cdot \hat{n}_i$$

---

## 3. SVG Smooth Path 與圓角端點構建

獲得 $L_i$ 與 $R_i$ 點集後，`build_stroke_ribbon()` 使用 SVG 繪製指令組合出封閉路徑：

```
[Start Cap (Arc A)] ──► [Right Side Smooth Quad Curves (Q)] ──► [End Cap (Arc A)] ──► [Left Side Smooth Quad Curves (Q)] ──► Close (Z)
```

```python
# 圓角收頭與平滑控制指令 (build_stroke_ribbon 關鍵片段)
d = [f"M {left_side[0][0]:.2f} {left_side[0][1]:.2f}"]
# 1. 起始端圓角 Arc (A)
d.append(f"A {r0:.2f} {r0:.2f} 0 0 1 {right_side[0][0]:.2f} {right_side[0][1]:.2f}")
# 2. 右側平滑二次貝茲曲線 Quadratic Bezier (Q)
d.extend(smooth_commands(right_side))
# 3. 結束端圓角 Arc (A)
d.append(f"A {r1:.2f} {r1:.2f} 0 0 1 {left_side[-1][0]:.2f} {left_side[-1][1]:.2f}")
# 4. 左側反向平滑二次貝茲曲線 Quadratic Bezier (Q)
d.extend(smooth_commands(reversed_left))
d.append("Z")
```

---

## 4. 橡皮擦切削與鋼筆筆跡 (`native_cgpaths` 原生向量幾何架構)

當使用者使用橡皮擦切斷/擦除筆跡，或書寫高精度鋼筆（Fountain Pen）筆跡時，GoodNotes 會直接執行布林幾何運算，並將完整的封閉向量輪廓路徑指令鏈（`native_cgpaths`）寫入經 Apple LZ4 壓縮的 TPL 二進位結構中。

### 1. 雙重 TPL 格式結構平移 (Schema Shift)

GoodNotes 6 儲存原生向量 CGPath 指令主要有兩種 TPL 格式變體：

| 格式屬性 | 變體 A（`vuA(v)...`，包含筆寬 `u`） | 變體 B（`vA(v)...`，不含筆寬 `u`） |
| :--- | :--- | :--- |
| **平移偏移量 (Shift)** | `shift = 1`（共 12 個欄位） | `shift = 0`（共 11 個欄位） |
| **每段面板指令數** | `values[5]` | `values[4]` |
| **操作指令碼** | `values[6]`（`{2, 4, 5}`） | `values[5]`（`{0, 2, 3}`） |
| **起點座標 `(x0, y0)`** | `values[7]` | `values[6]` |
| **三次貝茲曲線控制點 `(c1, c2, p2)`** | `values[9]` | `values[8]` |
| **圓弧幾何參數 `(cx, cy, r, a0, a1)`** | `values[10]` | `values[9]` |
| **圓弧順逆時針旗標 `(0 / 1)`** | `values[11]` | `values[10]` |

### 2. Apple CoreGraphics 指令碼映射

底層二進位指令碼對應至標準 Apple `CGPath` 原生繪圖操作：
- **`MoveTo`（變體 A: `CMD 2` / 變體 B: `CMD 0`）**：從起點池取出 `(x0, y0)` 移動畫筆。
- **`CubicTo`（變體 A: `CMD 4` / 變體 B: `CMD 2`）**：從三次曲線池取出 3 組座標 `(c1x, c1y, c2x, c2y, p2x, p2y)` 繪製平滑曲線。
- **`ArcTo`（變體 A: `CMD 5` / 變體 B: `CMD 3`）**：繪製圓弧 `(cx, cy, r, a0, a1, flag)`，對應 `CGPathAddArc`。

### 3. Apple `CGPathAddArc` 至 SVG `A` 弧線轉換

在螢幕座標系（$Y$ 軸向下）中，圓弧轉換為 SVG 繪圖指令 `A rx ry 0 large_arc sweep end_x end_y`：
- 起點座標：$(cx + r\cos(a_0), cy + r\sin(a_0))$，與前一段貝茲曲線終點無縫接合（誤差 0.0000）。
- 終點座標：$(cx + r\cos(a_1), cy + r\sin(a_1))$。
- 旋轉方向與跨度計算：
  $$\Delta\theta = (a_0 - a_1) \pmod{2\pi}$$
  $$\text{sweep} = 0 \text{ if } \text{flag} == 1 \text{ else } 1, \quad \text{large\_arc} = 1 \text{ if } \Delta\theta > \pi \text{ else } 0$$

### 4. Nonzero 環繞規則與次像素接縫補全 (Subpixel Seam Bridging)

- **Nonzero 填充規則**：筆跡由數十個微重疊的封閉四邊形面板（Panels）連續組成。在 SVG 預設的 `fill-rule="nonzero"` 規則下，所有同向環繞的重疊面板會平滑融合成 100% 實心無縫筆跡（避免了 `evenodd` 產生的偶數重疊鏤空孔洞）。
- **次像素抗鋸齒接縫補全**：瀏覽器與 PDF 向量光柵化器在相鄰面板邊緣常因次像素抗鋸齒產生極細微白線（縫隙）。繪製時透過疊加同色微細外框線（`stroke="{s_color}" stroke-width="{0.4 * dpi_scale}" stroke-linejoin="round"`）完全消除接縫空洞。

### 5. 套索移動變換矩陣傳遞 (Lasso Move Transformation)

當使用者使用套索工具（Lasso Tool）移動筆跡時，Protobuf Trailer 中記錄的相對位移 $(dx, dy)$ 會自動遞迴套用至 `native_cgpaths` 中所有起點座標、三次貝茲控制點與圓弧圓心，確保移動後的向量筆跡維持在正確畫布座標。

---

## 5. 抖動過濾與異常跳躍安全防護 (Jitter & Split Safety)

### 1. 抖動過濾比率 (`_path_jitter_ratio`)
有時某些陣列剛好符合座標數值範圍，但實際上是筆劃的方向/切線元數據而非路徑點。
我們計算相鄰向量的方向反轉率：

$$\text{Jitter Ratio} = \frac{\text{方向反轉次數 (Cos angle } < -0.3\text{)}}{\text{總向量段數}}$$

正常筆跡的 Jitter Ratio 通常小於 `0.25`，若超過閾值 `_JITTER_REJECT_THRESHOLD = 0.35`，則判定為元數據陣列並予以過濾。

### 2. 距離切割防護 (`split_stroke_points`)
當兩個相鄰控制點之間的距離超過安全門檻 `300.0` points 時，表示該處存在點位跳躍或抬筆未記錄。`split_stroke_points()` 會將其安全切斷為獨立子筆跡，避免繪製出穿過整張頁面的錯誤直線。

---

在下一章 **[05 - 圖形、文字與頁面元素](05-shapes-text-and-elements#中文)** 中，我們將介紹向量圖形 (Shapes)、箭頭 Marker、富文本框與圖片裁切 (Crop) 的解析細節。
