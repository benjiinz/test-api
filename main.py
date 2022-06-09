from fastapi import FastAPI, UploadFile
from PIL import Image
from starlette.responses import StreamingResponse
from typing import Union
import io


import aiohttp
import asyncpg


app = FastAPI()

session = None

@app.on_event('startup') #starts a Client session and connects to DB on app startup
async def startup_event():
    global session
    session = aiohttp.ClientSession()
    global pool
    pool = await asyncpg.create_pool('postgresql://postgres@localhost/imagesapi', password = '1234')
    

@app.on_event('shutdown') # shuts session and DB connection down
async def shutdown_event():
    await session.close()
    await pool.close()


# takes upload file, converts to rgb (gets rid of transaparency), optional quality parameter

@app.post("/uploadfile")
async def post_picture(img: UploadFile, quality: Union[int, None] = None):
    request_object_content = await img.read()
    im = Image.open(io.BytesIO(request_object_content))
    rgb_im = im.convert('RGB')
    buf = io.BytesIO()
    if quality:
        rgb_im.save(buf, format='JPEG', quality = quality, optimize = True)
    else:
        rgb_im.save(buf, format='JPEG')
    byte_im = buf.getvalue()
    await pool.execute('''
        INSERT INTO image(img) VALUES ($1)
    ''', byte_im)
    return None

# DB uses sequential IDs, may be changed to assigned IDs if needed 
# (Therefore no id in POST function)
# Image returned via bytes array streaming, thought creating temp files to send would be space consuming


@app.get("/picture/{id}")
async def get_picture(id: int):
    result = await pool.fetch('''
        SELECT img FROM image
        WHERE id = ($1)
    ''', id)
    byte_im = result[0]['img']
    return StreamingResponse(io.BytesIO(byte_im), media_type = "image/jpg")
    
    





