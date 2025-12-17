from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


def create_app(redis_client):
    """
    Create and configure the FastAPI application.

    The application does not perform any heavy computation itself.
    All ranking logic is assumed to be handled upstream and stored
    in Redis as a sorted set.
    """

    app = FastAPI()

    # Allow cross-origin requests (frontend may be hosted separately)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Serve static frontend assets
    app.mount(
        "/frontend",
        StaticFiles(directory="frontend"),
        name="frontend",
    )

    @app.get("/")
    async def index():
        """Serve the frontend entry point."""
        return FileResponse("frontend/index.html")

    @app.get("/leaderboard")
    async def leaderboard(page: int = 1, limit: int = 25):
        """
        Return a paginated leaderboard ordered by descending score.
        """

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
                    "user": user,
                    "prob": float(score),
                }
                for i, (user, score) in enumerate(data)
            ],
        }

    return app
