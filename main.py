from asyncio.log import logger
from fastapi import FastAPI, UploadFile, Depends, status, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from PIL import Image
from starlette.responses import StreamingResponse
from typing import Union
import io
import logging
from logging.handlers import TimedRotatingFileHandler
from pydantic import BaseModel
from auth.auth_handler import sign_JWT
from auth.auth_bearer import JWTBearer


import aiohttp
import asyncpg

FORMAT = '%(asctime)s,%(msecs)d: %(Funcname)s: %(levelname)s: %(message)s'

formatter = logging.Formatter(FORMAT)

handler = TimedRotatingFileHandler('logs/app.log', 
                                   when='midnight',
                                   backupCount=10)
handler.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

app = FastAPI()

class User(BaseModel):
    username: str
    password: str

session = None



@app.on_event('startup') # starts a Client session and connects to DB on app startup
async def startup_event():
    global session
    session = aiohttp.ClientSession()
    global pool
    global userspool
    pool = await asyncpg.create_pool('postgresql://postgres@localhost/imagesapi', password = '1234')
    userspool = await asyncpg.create_pool('postgresql://postgres@localhost/users', password = '1234')
    

@app.on_event('shutdown') # shuts session and DB connection down
async def shutdown_event():
    await session.close()
    await pool.close()
    await userspool.close()

@app.post('/user/signup')
async def create_user(user: User = Body(...)):
    await userspool.execute(
        '''
        INSERT INTO user_table VALUES ($1, $2)
        ''', user.username, user.password
    )
    logger.info('New user created')
    return sign_JWT(user.username)


async def check_user(data: User):
    check_result = await userspool.fetch('''
        SELECT username FROM user_table
        WHERE (username = $1) AND (password = $2)
    ''', data.username, data.password)
    if len(check_result) == 0:
        return False
    return True


@app.post("/user/login")
async def user_login(user: User = Body(...)):
    if check_user(user):
        return sign_JWT(user.username)
    logger.info('Unsuccessful login attempt')
    return {
        "error": "Wrong login details!"
    }


@app.post("/uploadfile", dependencies=[Depends(JWTBearer())])
async def post_picture(img: UploadFile, quality: Union[int, None] = None, x: Union[int, None] = None, y: Union[int, None] = None):
    request_object_content = await img.read()
    im = Image.open(io.BytesIO(request_object_content))
    rgb_im = im.convert('RGB')
    buf = io.BytesIO()
    if x and y:
        rgb_im = rgb_im.resize((x,y), Image.ANTIALIAS)
        logger.info(f'Resized image to ({x},{y})')

    if quality:
        rgb_im.save(buf, format='JPEG', quality = quality, optimize = True)
        logger.info(f'Compressed image to {quality}%')
    else:
        rgb_im.save(buf, format='JPEG')
    byte_im = buf.getvalue()
    await pool.execute('''
        INSERT INTO image(img) VALUES ($1)
    ''', byte_im)
    logger.info('Sent Image into Database')
    return None

# DB uses sequential IDs, may be changed to assigned IDs if needed 
# (Therefore no id in POST function)
# Image returned via bytes array streaming, thought creating temp files to send would be space consuming


@app.get("/picture/{id}", dependencies=[Depends(JWTBearer())])
async def get_picture(id: int):
    result = await pool.fetch('''
        SELECT img FROM image
        WHERE id = ($1)
    ''', id)
    byte_im = result[0]['img']
    logger.info(f'Responded with Image of ID {id}')
    return StreamingResponse(io.BytesIO(byte_im), media_type = "image/jpg")


@app.get("/logs")
async def get_logs(date: Union[str, None] = None):
    if date:
        with open(f'logs/app.log.{str}', 'r') as f:
            data = f.readlines()
            return {f'logfile for {date}': data}
    else:
        with open(f'logs/app.log', 'r') as f:
            data = f.readlines()
            return {f'logfile for today': "".join(data)}



