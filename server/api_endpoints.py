from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os


def create_app(redis_client):
    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static directory
    app.mount(
        "/frontend",
        StaticFiles(directory="frontend"),
        name="frontend",
    )

    @app.get("/")
    async def index():
        return FileResponse("frontend/index.html")

    @app.get("/leaderboard")
    async def leaderboard(page: int = 1, limit: int = 25):
        start = (page - 1) * limit
        end = start + limit - 1

        data = await redis_client.zrevrange(
            "leaderboard",
            start,
            end,
            withscores=True,
        )

        total = await redis_client.zcard("leaderboard")

        return {
            "page": page,
            "limit": limit,
            "total": total,
            "results": [
                {
                    "rank": start + i + 1,
                    "user": u,
                    "prob": float(p),
                }
                for i, (u, p) in enumerate(data)
            ],
        }

    return app
