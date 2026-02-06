# from pydantic import 
import uuid
from sqlmodel import Field,SQLModel

class UserBase(SQLModel):
    tel:str = Field(unique=True,index=True,max_length=11,min_length=6)
    name:str = Field(max_length=255)

class User(SQLModel,table=True):
    id:uuid.UUID = Field(default_factory=uuid.uuid4,primary_key=True)
    hashed_password:str