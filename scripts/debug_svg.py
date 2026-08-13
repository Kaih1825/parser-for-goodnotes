import re

with open('samples/NewGN6_out/page_1_notes_37DCB0D5-ADD2-42AF-82F8-D8E23BA8D93F.svg') as f:
    content = f.read()

# background SVG 是第二個 <svg> 元素
first_svg_end = content.find('>', content.find('<svg')) + 1
second_svg_start = content.find('<svg', first_svg_end)
print('Second SVG tag:')
print(content[second_svg_start:second_svg_start+300])
print('---')

# 找背景 SVG 結尾（第一個 </svg>）
end_tag = content.find('</svg>', second_svg_start)
bg_section = content[second_svg_start:end_tag]
print(f'Background section length: {len(bg_section)}')

# 找藍色相關顏色
all_fills = re.findall(r'fill="([^"]+)"', bg_section)
from collections import Counter
print('Fill colors in background:', Counter(all_fills).most_common(10))

# 找最大的 path
paths = re.findall(r'd="([^"]+)"', bg_section)
print(f'Paths in background: {len(paths)}')
results = []
for p in paths:
    nums = re.findall(r'[-+]?\d+\.?\d*', p)
    fs = [float(n) for n in nums[:200]]
    if len(fs) < 4:
        continue
    xs = fs[0::2]
    ys = fs[1::2]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    results.append((( x_max - x_min) * (y_max - y_min), x_min, x_max, y_min, y_max, p[:80]))

results.sort(reverse=True)
print('Top 5 paths:')
for area, x1, x2, y1, y2, snippet in results[:5]:
    print(f'  area={area:.0f} x=[{x1:.1f},{x2:.1f}] y=[{y1:.1f},{y2:.1f}]')
    print(f'  {snippet}')
