import fitz
from PIL import Image
import sys
import numpy as np

sys.path.insert(0, '/Users/kai/Desktop/DevSpace/Goodnotes/src')

from goodnotes_re.archive import GoodNotesDocument
from goodnotes_re.export import page_to_svg

real_img = Image.open('/Users/kai/Desktop/DevSpace/Goodnotes/output_svgs/real-1.jpg').convert('L')
w_real, h_real = real_img.size

svg_path = '/Users/kai/Desktop/DevSpace/Goodnotes/output_svgs/page_2_notes_772788D6-C0D0-4A7D-982E-4607E6DCC1D4.svg'
doc_svg = fitz.open(svg_path)
rect = doc_svg[0].rect
mat = fitz.Matrix(w_real / rect.width, h_real / rect.height)
pix = doc_svg[0].get_pixmap(matrix=mat)
our_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert('L')

real_arr = np.array(real_img)
our_arr = np.array(our_img)

# Threshold: Paper background is > 200 (paper dots are 205-240). True purple ink is < 180.
mask_real = real_arr < 180
mask_our = our_arr < 180

matched = int(np.sum(mask_real & mask_our))
missing = int(np.sum(mask_real & (~mask_our)))
extra = int(np.sum((~mask_real) & mask_our))

# Generate high-contrast color diff
comp = np.full((h_real, w_real, 3), 255, dtype=np.uint8)
comp[mask_real & mask_our] = [130, 33, 139]       # Purple: Matched
comp[mask_real & (~mask_our)] = [255, 0, 0]        # Red: Missing (in real, not in our)
comp[(~mask_real) & mask_our] = [0, 150, 255]      # Blue: Extra (in our, not in real)

diff_img = Image.fromarray(comp)
diff_img.save('/Users/kai/Desktop/DevSpace/Goodnotes/output_svgs/diff.png')
diff_img.save('/Users/kai/.gemini/antigravity-ide/brain/346e5e17-560f-4427-93bf-c197b6fcf58a/scratch/diff.png')

total = matched + missing + extra
rate = matched / total if total > 0 else 0
print(f"Match Rate: {rate * 100:.2f}% (Matched: {matched}, Missing Red: {missing}, Extra Blue: {extra})")
print("Diff image saved to output_svgs/diff.png")
