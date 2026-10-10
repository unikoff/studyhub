from typing import Annotated

from fastapi import APIRouter, Header, Response


router = APIRouter(tags=["preferences"])


@router.get("/preferences")
def read_preferences(
    response: Response,
    client_version: Annotated[
        str | None,
        Header(alias="X-Client-Version", max_length=64),
    ] = None,
):
    response.headers["X-Planner-Version"] = "1"
    return {
        "view": "compact",
        "client_version": client_version,
    }
