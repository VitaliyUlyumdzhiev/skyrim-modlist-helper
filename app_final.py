from fastapi import FastAPI


APP_VERSION = "0.1.0"

app = FastAPI(
    title="Skyrim Modlist Helper",
    version=APP_VERSION,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/version")
def version():
    return {"version": APP_VERSION}