from typing import Annotated

from fastapi import APIRouter, Cookie, Header, Response, status

from .schemas import PreferenceRead, PreferenceView, PreferenceWrite


router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=PreferenceRead)
def read_preferences(
    response: Response,
    client_version: Annotated[
        str | None,
        Header(alias="X-Client-Version", max_length=64),
    ] = None,
    planner_view: str | None = Cookie(default=None),
) -> PreferenceRead:
    view: PreferenceView = (
        planner_view
        if planner_view in {"compact", "detailed"}
        else "compact"
    )
    response.headers["X-Planner-Version"] = "1"
    return PreferenceRead(view=view, client_version=client_version)


@router.put("", response_model=PreferenceRead)
def set_preferences(
    payload: PreferenceWrite,
    response: Response,
    client_version: Annotated[
        str | None,
        Header(alias="X-Client-Version", max_length=64),
    ] = None,
) -> PreferenceRead:
    response.set_cookie(
        key="planner_view",
        value=payload.view,
        path="/preferences",
        httponly=True,
        secure=False,
        samesite="lax",
    )
    response.headers["X-Planner-Version"] = "1"
    return PreferenceRead(view=payload.view, client_version=client_version)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def reset_preferences(response: Response) -> Response:
    response.delete_cookie(key="planner_view", path="/preferences")
    response.headers["X-Planner-Version"] = "1"
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
