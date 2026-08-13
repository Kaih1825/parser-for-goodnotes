import sys, zipfile
sys.path.insert(0, 'src')

from goodnotes_re.stroke import parse_stroke_field, decode_tpl, uint32_to_float32
from goodnotes_re.wire import decode_message
from goodnotes_re.compression import decode_apple_lz4

with open('samples/NewGN6.goodnotes', 'rb') as f:
    with zipfile.ZipFile(f) as z:
        raw = z.read('notes/37DCB0D5-ADD2-42AF-82F8-D8E23BA8D93F')

msg = decode_message(raw)
fields_22 = msg.by_number(22)
print(f'Number of field-22 records: {len(fields_22)}')

count = 0
for fi, f22 in enumerate(fields_22):
    if not isinstance(f22.value, bytes):
        continue
    strokes = parse_stroke_field(str(fi), f22.value)
    for s in strokes:
        if 'vA(v)A(u)' in s.tpl_format and s.width > 5:
            print(f'\nBad stroke #{fi}: width={s.width:.2f} tpl={s.tpl_format!r}')
            pos = f22.value.find(b'bv41')
            if pos >= 0:
                lz4_data, _ = decode_apple_lz4(f22.value[pos:])
                tpl_img = decode_tpl(lz4_data)
                print(f'  format: {tpl_img.format!r}')
                print(f'  values count: {len(tpl_img.values)}')
                for i, v in enumerate(tpl_img.values[:8]):
                    if isinstance(v, int):
                        f32 = uint32_to_float32(v)
                        print(f'  values[{i}] int={v} => float32={f32:.6f}')
                    elif isinstance(v, list):
                        print(f'  values[{i}] list len={len(v)}: {v[:4]}')
            count += 1
            if count >= 3:
                break
    if count >= 3:
        break
