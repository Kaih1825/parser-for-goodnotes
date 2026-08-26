import fitz
from PIL import Image, ImageOps
import sys
sys.path.insert(0, '/Users/kai/Desktop/DevSpace/Goodnotes/src')

from goodnotes_re.archive import GoodNotesDocument
from goodnotes_re.export import page_to_svg

real = Image.open('/Users/kai/Desktop/DevSpace/Goodnotes/output_svgs/real-1.jpg').convert('L')
w_real, h_real = real.size
real_stroke = ImageOps.invert(real).point(lambda p: 255 if p > 30 else 0)

with GoodNotesDocument.open('/Users/kai/Desktop/DevSpace/Goodnotes/samples/era.goodnotes') as doc:
    pages = doc.pages()
    svg_str = page_to_svg(pages[0], doc)
    
    doc_svg = fitz.open(stream=svg_str.encode("utf-8"), filetype="svg")
    rect = doc_svg[0].rect
    mat = fitz.Matrix(w_real / rect.width, h_real / rect.height)
    pix = doc_svg[0].get_pixmap(matrix=mat)
    
    our = Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert('L')
    our_stroke = ImageOps.invert(our).point(lambda p: 255 if p > 30 else 0)
    
    comp = Image.new('RGB', (w_real, h_real), (255, 255, 255))
    r_d = real_stroke.load()
    o_d = our_stroke.load()
    c_d = comp.load()
    
    matched, missing, extra = 0, 0, 0
    for y in range(h_real):
        for x in range(w_real):
            r = r_d[x, y] > 100
            u = o_d[x, y] > 100
            if r and u:
                c_d[x, y] = (128, 0, 128)
                matched += 1
            elif r and not u:
                c_d[x, y] = (255, 0, 0)
                missing += 1
            elif not r and u:
                c_d[x, y] = (0, 150, 255)
                extra += 1
                
    comp.save('/Users/kai/Desktop/DevSpace/Goodnotes/output_svgs/diff.png')
    total = matched + missing + extra
    rate = matched / total if total > 0 else 0
    print(f"Match Rate: {rate * 100:.2f}% (Matched: {matched}, Missing Red: {missing}, Extra Blue: {extra})")
