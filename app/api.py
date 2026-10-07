from fastapi import FastAPI

app = FastAPI(title="StudyHub Planner")


@app.get("/health")
def health_check():
    return {"status": "ok"}
