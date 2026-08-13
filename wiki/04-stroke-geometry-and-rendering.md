# 04 - 筆跡幾何與向量 Ribbon 重建 (Stroke Geometry & Rendering)

本章節詳細說明 **GoodNotes Document Parser** 如何將 Troy Hanson TPL 提取出的控制點與壓感資料，數學化重建為平滑、具備自然寬度變化的向量 SVG Path Ribbon（帶狀路徑），以及處理被橡皮擦局部擦除切開的筆跡（`v9` Native Mesh）。

---

## 1. 筆跡點與壓感模型 (Stroke Point & Pressure Model)

每一條筆跡由一系列帶有壓感值的控制點組成。在 [`src/goodnotes_re/stroke.py`](../src/goodnotes_re/stroke.py) 中定義為 `StrokePoint`：

```python
@dataclass(frozen=True)
class StrokePoint:
    x: float
    y: float
    pressure: float = 1.0  # 半徑或相對壓感比例
```

若 TPL 點陣中未包含顯式壓感（如單純 2D 座標），則使用由二進制表頭提取的 `default_width` 的一半（即預設半徑 $r = \text{width} / 2.0$）作為基礎壓感。

---

## 2. 變寬 Ribbon 法向量演算法 (Variable-Width Ribbon Algorithm)

直接使用 SVG `stroke-width` 繪製折線無法呈現真實手寫筆尖（如鋼筆、書法筆）隨壓感與速度變化的粗細效果。本工具包採用 **法向量偏移雙側輪廓 (Bi-lateral Offset Outlines)** 演算法，產生封閉的 2D 向量多邊形 Ribbon。

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

獲得 $L_i$ 與 $R_i$ 點集後，[`build_stroke_ribbon()`](../src/goodnotes_re/stroke.py) 使用 SVG 繪製指令組合出封閉路徑：

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

## 4. 被橡皮擦切開筆跡 (`v9` Mesh) 與滑動視窗凸包演算法

當使用者在 GoodNotes 中使用橡皮擦擦除筆跡的一部分時，GoodNotes 會生成 `v9` 陣列（位於 TPL `values[9]`）。

### `v9` 陣列的格式分析發現
經由 `dump_v9_to_svg_html` 視覺化格式分析發現：`v9` 陣列**並不是外框的連續走訪順序**，而是每 6 個點為一組、代表沿筆劃前進方向橫截面左右兩側的取樣點。在筆跡彎曲劇烈或收尖處，直接用 `L` (Line) 連接會產生鋸齒與自我交叉缺口。

### 解法：滑動視窗凸包 (Sliding-Window Convex Hull)

本工具包採用了不依賴分組是否對齊的**滑動視窗凸包算法 (`_v9_polygon_to_hull_panels`)**：

1. 設定滑動視窗大小 `window = 16`，步長 `stride = 4`。
2. 在 `v9` 點陣上移動視窗，對視窗內的點集計算 **Andrew's Monotone Chain 凸包**。
3. 視窗之間刻意重疊 (`stride < window`)，確保凸包面板彼此相接、完全不留縫隙。
4. 由於視窗範圍很小，橡皮擦切出的銳利平頭邊緣（Flat Cut Caps）不會被磨圓。

```python
def _convex_hull(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Andrew's monotone chain 凸包演算法。Pure-python 實現。"""
    pts = sorted(set(points))
    if len(pts) <= 2: return list(pts)
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0: lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0: upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]
```

---

## 5. 抖動過濾與異常跳躍安全防護 (Jitter & Split Safety)

### 1. 抖動過濾比率 (`_path_jitter_ratio`)
在 TPL 中，有時某些二進制陣列剛好符合座標數值範圍，但實際上是筆劃的方向/切線元數據而非路徑點。
本工具包計算相鄰向量的方向反轉率：

$$\text{Jitter Ratio} = \frac{\text{方向反轉次數 (Cos angle } < -0.3\text{)}}{\text{總向量段數}}$$

正常筆跡的 Jitter Ratio 通常小於 `0.25`，若超過閾值 `_JITTER_REJECT_THRESHOLD = 0.35`，則判定為元數據陣列並予以過濾。

### 2. 距離切割防護 (`split_stroke_points`)
當 TPL 中兩個相鄰控制點之間的距離超過安全門檻 `300.0` points 時，表示該處存在點位跳躍或抬筆未記錄。`split_stroke_points()` 會將其安全切斷為獨立子筆跡，避免繪製出穿過整張頁面的錯誤直線。

---

在下一章 **[05 - 圖形、文字與頁面元素](05-shapes-text-and-elements.md)** 中，我們將介紹向量圖形 (Shapes)、箭頭 Marker、富文本框與圖片裁切 (Crop) 的解析細節。
