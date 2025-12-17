from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def create_app(redis_client):
    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],   # OK for local dev
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/leaderboard")
    async def leaderboard(page: int = 1, limit: int = 25):
        start = (page - 1) * limit
        end = start + limit - 1

        data = await redis_client.zrevrange(
            "leaderboard",
            start,
            end,
            withscores=True
        )

        total = await redis_client.zcard("leaderboard")

        return {
            "page": page,
            "limit": limit,
            "total": total,
            "results": [
                {
                    "rank": start + i + 1,
                    "user": u.decode(),
                    "prob": float(p),
                }
                for i, (u, p) in enumerate(data)
            ]
        }

    return app
