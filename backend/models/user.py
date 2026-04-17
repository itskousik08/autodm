from pydantic import BaseModel


class User(BaseModel):
    instagram_id: str
    username: str
    access_token: str
