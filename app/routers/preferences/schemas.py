from typing import Literal

from pydantic import BaseModel


PreferenceView = Literal["compact", "detailed"]


class PreferenceWrite(BaseModel):
    view: PreferenceView


class PreferenceRead(BaseModel):
    view: PreferenceView
    client_version: str | None = None
