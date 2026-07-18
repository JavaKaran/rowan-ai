from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Health(BaseModel):
    message: str

@app.get("/healthy", response_model=Health)
async def healthy() -> Health:
    return Health(message="Service is healthy")
