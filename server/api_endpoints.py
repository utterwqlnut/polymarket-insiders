from fastapi import FastAPI

def create_app(redis_client):
    app = FastAPI()

    @app.get("/")
    async def leaderboard():
        data = await redis_client.zrevrange(
            "leaderboard",
            0,
            -1,
            withscores=True
        )
        return [{"user": u, "prob": p} for u, p in data]

    return app