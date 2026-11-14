"""A renderer-independent glass mask which excludes the entire portrait frame."""
import base64,io
from functools import lru_cache
from PIL import Image,ImageDraw,ImageChops


@lru_cache(maxsize=2)
def joined_glass(theme):
    scale=8
    outer=Image.new('L',(128*scale,160*scale))
    ImageDraw.Draw(outer).rounded_rectangle((0,0,128*scale-1,160*scale-1),radius=14*scale,fill=255)
    portrait=Image.new('L',outer.size)
    ImageDraw.Draw(portrait).rounded_rectangle((0,0,128*scale-1,128*scale-1),radius=14*scale,fill=255)
    # The difference fills only the two lower corner cutouts and the name plate.
    mask=ImageChops.subtract(outer,portrait).resize((256,320),Image.Resampling.LANCZOS)
    # Resampling can leak alpha back across the curved cutout. Crop again at
    # the final pixel size so every pixel inside the portrait remains empty.
    outside=Image.new('L',mask.size,255)
    ImageDraw.Draw(outside).rounded_rectangle((0,0,255,255),radius=28,fill=0)
    mask=ImageChops.multiply(mask,outside)
    image=Image.new('RGBA',mask.size,(20,32,50,0) if theme=='dark' else (248,251,255,0))
    image.putalpha(mask.point(lambda n:round(n*.5)))
    buffer=io.BytesIO();image.save(buffer,'PNG',optimize=True)
    return 'data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode('ascii')
