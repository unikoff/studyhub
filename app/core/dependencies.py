from fastapi import Request

from app.services import PlannerService


def get_planner(request: Request) -> PlannerService:
    return request.app.state.planner
