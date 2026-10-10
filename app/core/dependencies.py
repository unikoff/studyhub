from typing import Annotated

from fastapi import Depends, Request

from app.services import PlannerService


def get_planner(request: Request) -> PlannerService:
    return request.app.state.planner


PlannerDep = Annotated[PlannerService, Depends(get_planner)]
