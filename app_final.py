import logging
import os
from contextlib import asynccontextmanager
from threading import Lock

from fastapi import FastAPI, HTTPException, Path, Query
from pydantic import BaseModel, Field, field_validator

from nexus_client import fetch_nexus_mod


APP_VERSION = "0.1.0"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

if LOG_LEVEL not in {
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
}:
    LOG_LEVEL = "INFO"

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("skyrim_modlist_helper")
logger.setLevel(LOG_LEVEL)

catalog_lock = Lock()


class Mod(BaseModel):
    id: int
    name: str
    category: str
    description: str
    nexus_url: str
    requires: list[int] = Field(default_factory=list)
    dependency_data_available: bool = False
    source: str


class BuildRequest(BaseModel):
    mod_ids: list[int] = Field(min_length=1, max_length=50)

    @field_validator("mod_ids")
    @classmethod
    def validate_mod_ids(cls, values: list[int]) -> list[int]:
        if any(value <= 0 for value in values):
            raise ValueError("Mod IDs must be positive")

        if len(values) != len(set(values)):
            raise ValueError("Duplicate mod IDs are not allowed")

        return values


class MissingDependency(BaseModel):
    mod_id: int
    requires_mod_id: int


class BuildResult(BaseModel):
    selected_mod_ids: list[int]
    known_dependencies_satisfied: bool
    missing_dependencies: list[MissingDependency]
    unchecked_mod_ids: list[int]
    note: str


DEMO_MODS = {
    30379: Mod(
        id=30379,
        name="Skyrim Script Extender (SKSE64)",
        category="utilities",
        description="Select files matching your game version.",
        nexus_url=(
            "https://www.nexusmods.com/"
            "skyrimspecialedition/mods/30379"
        ),
        source="demo",
    ),
    12604: Mod(
        id=12604,
        name="SkyUI",
        category="interface",
        description="Interface overhaul for Skyrim Special Edition.",
        nexus_url=(
            "https://www.nexusmods.com/"
            "skyrimspecialedition/mods/12604"
        ),
        requires=[30379],
        dependency_data_available=True,
        source="demo",
    ),
    659: Mod(
        id=659,
        name="Static Mesh Improvement Mod",
        category="graphics",
        description="Visual improvements for static objects.",
        nexus_url=(
            "https://www.nexusmods.com/"
            "skyrimspecialedition/mods/659"
        ),
        source="demo",
    ),
    266: Mod(
        id=266,
        name="Unofficial Skyrim Special Edition Patch",
        category="patches",
        description="Check current requirements on Nexus Mods.",
        nexus_url=(
            "https://www.nexusmods.com/"
            "skyrimspecialedition/mods/266"
        ),
        source="demo",
    ),
}

catalog = dict(DEMO_MODS)


def catalog_snapshot() -> dict[int, Mod]:
    with catalog_lock:
        return dict(catalog)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Application started: version=%s catalog_size=%s",
        APP_VERSION,
        len(catalog_snapshot()),
    )
    yield
    logger.info("Application stopped")


app = FastAPI(
    title="Skyrim Modlist Helper",
    description=(
        "Search a local catalog, import mod details from Nexus Mods "
        "and check explicitly listed dependencies."
    ),
    version=APP_VERSION,
    lifespan=lifespan,
)


@app.get("/health", tags=["Service"])
def health():
    return {"status": "ok"}


@app.get("/version", tags=["Service"])
def version():
    return {"version": APP_VERSION}


@app.get("/mods", response_model=list[Mod], tags=["Mods"])
def list_mods(
    category: str | None = Query(default=None),
):
    mods = list(catalog_snapshot().values())

    if category is not None:
        category = category.strip().lower()
        mods = [
            mod
            for mod in mods
            if mod.category.lower() == category
        ]

    logger.info("Catalog requested: results=%s", len(mods))
    return sorted(mods, key=lambda mod: mod.id)


# This route must be declared before /mods/{mod_id}.
@app.get("/mods/search", response_model=list[Mod], tags=["Mods"])
def search_mods(
    q: str = Query(min_length=1, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    query = q.strip().casefold()

    if not query:
        raise HTTPException(
            status_code=422,
            detail="Search query must not be blank",
        )

    results = [
        mod
        for mod in catalog_snapshot().values()
        if query in mod.name.casefold()
        or query in mod.description.casefold()
    ]

    results.sort(key=lambda mod: mod.id)

    logger.info("Search completed: matches=%s", len(results))

    return results[offset:offset + limit]


@app.get("/mods/{mod_id}", response_model=Mod, tags=["Mods"])
def get_mod(
    mod_id: int = Path(gt=0),
):
    mod = catalog_snapshot().get(mod_id)

    if mod is None:
        raise HTTPException(
            status_code=404,
            detail="Mod was not found in the local catalog",
        )

    return mod


@app.get("/categories", response_model=list[str], tags=["Mods"])
def categories():
    return sorted(
        {mod.category for mod in catalog_snapshot().values()}
    )


@app.post(
    "/build/check",
    response_model=BuildResult,
    tags=["Build"],
)
def check_build(build: BuildRequest):
    mods = catalog_snapshot()
    selected_ids = set(build.mod_ids)

    unknown_ids = sorted(selected_ids - set(mods))

    if unknown_ids:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Some mods are not in the local catalog",
                "unknown_mod_ids": unknown_ids,
            },
        )

    missing = []
    unchecked = []

    for mod_id in build.mod_ids:
        mod = mods[mod_id]

        if not mod.dependency_data_available:
            unchecked.append(mod_id)

        for dependency_id in mod.requires:
            if dependency_id not in selected_ids:
                missing.append(
                    MissingDependency(
                        mod_id=mod_id,
                        requires_mod_id=dependency_id,
                    )
                )

    logger.info(
        "Build checked: selected=%s missing=%s unchecked=%s",
        len(selected_ids),
        len(missing),
        len(unchecked),
    )

    return BuildResult(
        selected_mod_ids=build.mod_ids,
        known_dependencies_satisfied=not missing,
        missing_dependencies=missing,
        unchecked_mod_ids=unchecked,
        note=(
            "Only explicitly listed dependencies were checked. "
            "Unchecked mods have no dependency data in this catalog. "
            "This result is not a compatibility guarantee."
        ),
    )


@app.get(
    "/nexus/mods/{mod_id}",
    response_model=Mod,
    tags=["Nexus Mods"],
)
async def import_nexus_mod(
    mod_id: int = Path(gt=0),
):
    api_key = os.getenv("NEXUS_API_KEY", "").strip()

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Nexus Mods integration is not configured",
        )

    try:
        timeout = float(
            os.getenv("NEXUS_TIMEOUT_SECONDS", "10")
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail="NEXUS_TIMEOUT_SECONDS must be a number",
        ) from exc

    if not 0 < timeout <= 60:
        raise HTTPException(
            status_code=503,
            detail="NEXUS_TIMEOUT_SECONDS must be between 0 and 60",
        )

    data = await fetch_nexus_mod(
        mod_id=mod_id,
        api_key=api_key,
        timeout=timeout,
    )

    imported = Mod(
        id=mod_id,
        name=data["name"],
        category="imported",
        description=str(data.get("summary") or ""),
        nexus_url=(
            "https://www.nexusmods.com/"
            f"skyrimspecialedition/mods/{mod_id}"
        ),
        source="nexus",
    )

    with catalog_lock:
        previous = catalog.get(mod_id)

        # Keep manually curated dependency information if available.
        if previous is not None:
            imported = imported.model_copy(
                update={
                    "category": previous.category,
                    "requires": previous.requires,
                    "dependency_data_available": (
                        previous.dependency_data_available
                    ),
                }
            )

        catalog[mod_id] = imported

    logger.info("Nexus mod imported: mod_id=%s", mod_id)

    return imported