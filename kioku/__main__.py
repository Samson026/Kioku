import os

import uvicorn


def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    reload = os.environ.get("RELOAD", "").lower() in {"1", "true", "yes"}
    uvicorn.run("kioku.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
