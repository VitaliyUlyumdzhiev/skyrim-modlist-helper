import logging

import httpx
from fastapi import HTTPException


logger = logging.getLogger("skyrim_modlist_helper.nexus")

NEXUS_BASE_URL = "https://api.nexusmods.com/v1"


async def fetch_nexus_mod(
    mod_id: int,
    api_key: str,
    timeout: float,
) -> dict:
    url = (
        f"{NEXUS_BASE_URL}/games/"
        f"skyrimspecialedition/mods/{mod_id}.json"
    )

    headers = {
        "apikey": api_key,
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)

    except httpx.TimeoutException as exc:
        logger.warning("Nexus Mods request timed out: mod_id=%s", mod_id)
        raise HTTPException(
            status_code=504,
            detail="Nexus Mods request timed out",
        ) from exc

    except httpx.RequestError as exc:
        logger.warning("Nexus Mods connection failed: mod_id=%s", mod_id)
        raise HTTPException(
            status_code=502,
            detail="Could not connect to Nexus Mods",
        ) from exc

    logger.info(
        "Nexus Mods response: mod_id=%s status=%s",
        mod_id,
        response.status_code,
    )

    if response.status_code in (401, 403):
        raise HTTPException(
            status_code=502,
            detail="Nexus Mods rejected authentication or access",
        )

    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Mod was not found on Nexus Mods",
        )

    if response.status_code == 429:
        raise HTTPException(
            status_code=503,
            detail="Nexus Mods API rate limit reached; try later",
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail="Nexus Mods returned an unexpected response",
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Nexus Mods returned invalid JSON",
        ) from exc

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=502,
            detail="Nexus Mods returned an unexpected data format",
        )

    name = data.get("name")

    if not isinstance(name, str) or not name.strip():
        raise HTTPException(
            status_code=502,
            detail="Nexus Mods response does not contain a valid mod name",
        )

    return data