from fastapi import FastAPI
import aiohttp
from PIL import Image

import asyncio

app = FastAPI()


@app.get("/")
def root():
    return {"message": "Hello World"}


@app.get("/items/{item_id}")
def read_item(item_id: int):
    return {"item_id" : item_id}

@app.get("/picture/{id}")
def fetch_picture(id: str):
    return

@app.post("/picture/{id}")
def post_picture(id: str, img: UploadFile)





