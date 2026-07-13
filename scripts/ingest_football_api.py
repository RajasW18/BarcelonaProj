"""
ingest_football_api.py
──────────────────────
Fetches live / recent data from football-data.org v4 API and upserts
into the PostgreSQL database.

Fetches:
  • FC Barcelona squad (team id 81)
  • La Liga matches (competition PD)
  • La Liga standings
  • Player statistics (appearances/goals — where available)

Usage:
    python scripts/ingest_football_api.py
    python scripts/ingest_football_api.py --season 2024  # specific season year
"""
import argparse
import asyncio
import sys
from datetime import date, datetime
from pathlib import Path

import asyncpg
import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))
from api.config import settings

BASE_URL = settings.football_data_base_url
BARCA_TEAM_ID = 81          # FC Barcelona
LA_LIGA_CODE  = "PD"        # Primera División

HEADERS = {"X-Auth-Token": settings.football_data_api_key}


# ─── Helpers ─────────────────────────────────────────────────────────────────
async def api_get(client: httpx.AsyncClient, path: str) -> dict:
    """GET from football-data.org with error handling."""
    r = await client.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def safe_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str[:10])
    except ValueError:
        return None


# ─── Upsert helpers ───────────────────────────────────────────────────────────
async def upsert_team(conn: asyncpg.Connection, team: dict) -> int:
    return await conn.fetchval(
        """
        INSERT INTO teams(api_id, name, short_name, tla, crest_url)
        VALUES($1,$2,$3,$4,$5)
        ON CONFLICT (api_id) DO UPDATE
            SET name=EXCLUDED.name, short_name=EXCLUDED.short_name,
                tla=EXCLUDED.tla, crest_url=EXCLUDED.crest_url
        RETURNING id
        """,
        team.get("id"),
        team.get("name", "Unknown"),
        team.get("shortName"),
        team.get("tla"),
        team.get("crest"),
    )


async def upsert_competition(
    conn: asyncpg.Connection, competition: dict, season: str
) -> int:
    return await conn.fetchval(
        """
        INSERT INTO competitions(api_id, code, name, area, season)
        VALUES($1,$2,$3,$4,$5)
        ON CONFLICT (api_id) DO UPDATE
            SET name=EXCLUDED.name, season=EXCLUDED.season
        RETURNING id
        """,
        competition.get("id"),
        competition.get("code"),
        competition.get("name", "Unknown"),
        competition.get("area", {}).get("name"),
        season,
    )


# ─── Ingestion steps ──────────────────────────────────────────────────────────
async def ingest_squad(client: httpx.AsyncClient, conn: asyncpg.Connection):
    """Fetch and upsert FC Barcelona squad."""
    print("  → Fetching FC Barcelona squad …")
    data = await api_get(client, f"/teams/{BARCA_TEAM_ID}")

    barca_db_id = await upsert_team(conn, data)

    squad = data.get("squad", [])
    for player in squad:
        await conn.execute(
            """
            INSERT INTO players
                (api_id, team_id, name, first_name, last_name,
                 position, nationality, date_of_birth, shirt_number)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)
            ON CONFLICT (api_id) DO UPDATE
                SET team_id=EXCLUDED.team_id,
                    name=EXCLUDED.name,
                    position=EXCLUDED.position,
                    shirt_number=EXCLUDED.shirt_number
            """,
            player.get("id"),
            barca_db_id,
            player.get("name"),
            player.get("firstName"),
            player.get("lastName") or player.get("name"),
            player.get("position"),
            player.get("nationality"),
            safe_date(player.get("dateOfBirth")),
            player.get("shirtNumber"),
        )
    print(f"     ✓ {len(squad)} players upserted")


async def ingest_matches(
    client: httpx.AsyncClient,
    conn: asyncpg.Connection,
    season: str,
):
    """Fetch and upsert La Liga matches for the given season."""
    print(f"  → Fetching La Liga matches (season {season}) …")
    data = await api_get(client, f"/competitions/{LA_LIGA_CODE}/matches?season={season}")

    matches = data.get("matches", [])
    competition_raw = data.get("competition", {})
    comp_db_id = await upsert_competition(conn, competition_raw, f"{season}/{str(int(season)+1)[-2:]}")

    for m in matches:
        home_raw = m.get("homeTeam", {})
        away_raw = m.get("awayTeam", {})
        if not home_raw.get("id") or not away_raw.get("id"):
            continue

        home_id = await upsert_team(conn, home_raw)
        away_id = await upsert_team(conn, away_raw)
        score = m.get("score", {}).get("fullTime", {})

        await conn.execute(
            """
            INSERT INTO matches
                (api_id, competition_id, season, matchday, match_date,
                 home_team_id, away_team_id, home_score, away_score,
                 status, stage, source)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,'football-data')
            ON CONFLICT (api_id) DO UPDATE
                SET home_score=EXCLUDED.home_score,
                    away_score=EXCLUDED.away_score,
                    status=EXCLUDED.status,
                    match_date=EXCLUDED.match_date
            """,
            m.get("id"),
            comp_db_id,
            f"{season}/{str(int(season)+1)[-2:]}",
            m.get("matchday"),
            datetime.fromisoformat(m.get("utcDate").replace("Z", "+00:00")) if m.get("utcDate") else None,
            home_id,
            away_id,
            score.get("home"),
            score.get("away"),
            m.get("status", "SCHEDULED"),
            m.get("stage"),
        )
    print(f"     ✓ {len(matches)} matches upserted")


async def ingest_standings(
    client: httpx.AsyncClient,
    conn: asyncpg.Connection,
    season: str,
):
    """Fetch and upsert La Liga standings."""
    print(f"  → Fetching La Liga standings (season {season}) …")
    data = await api_get(client, f"/competitions/{LA_LIGA_CODE}/standings?season={season}")

    competition_raw = data.get("competition", {})
    comp_db_id = await upsert_competition(
        conn, competition_raw, f"{season}/{str(int(season)+1)[-2:]}"
    )

    season_label = f"{season}/{str(int(season)+1)[-2:]}"
    standings = data.get("standings", [])
    for group in standings:
        if group.get("type") != "TOTAL":
            continue
        for entry in group.get("table", []):
            team_raw = entry.get("team", {})
            if not team_raw.get("id"):
                continue
            team_db_id = await upsert_team(conn, team_raw)

            await conn.execute(
                """
                INSERT INTO standings
                    (competition_id, season, team_id, position,
                     played_games, won, draw, lost,
                     goals_for, goals_against, goal_difference, points, form)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                ON CONFLICT (competition_id, season, team_id) DO UPDATE
                    SET position=EXCLUDED.position,
                        played_games=EXCLUDED.played_games,
                        won=EXCLUDED.won, draw=EXCLUDED.draw, lost=EXCLUDED.lost,
                        goals_for=EXCLUDED.goals_for,
                        goals_against=EXCLUDED.goals_against,
                        goal_difference=EXCLUDED.goal_difference,
                        points=EXCLUDED.points,
                        form=EXCLUDED.form,
                        updated_at=NOW()
                """,
                comp_db_id,
                season_label,
                team_db_id,
                entry.get("position"),
                entry.get("playedGames"),
                entry.get("won"),
                entry.get("draw"),
                entry.get("lost"),
                entry.get("goalsFor"),
                entry.get("goalsAgainst"),
                entry.get("goalDifference"),
                entry.get("points"),
                entry.get("form"),
            )
    print(f"     ✓ standings upserted")


# ─── Main ─────────────────────────────────────────────────────────────────────
async def main(season: str):
    if not settings.football_data_api_key:
        print("❌ FOOTBALL_DATA_API_KEY not set in .env — aborting.")
        sys.exit(1)

    pool = await asyncpg.create_pool(dsn=settings.database_url)
    async with httpx.AsyncClient() as client:
        async with pool.acquire() as conn:
            await ingest_squad(client, conn)
            await ingest_matches(client, conn, season)
            await ingest_standings(client, conn, season)

    await pool.close()
    print("\n✅ football-data.org ingestion complete!")


if __name__ == "__main__":
    current_year = date.today().year
    parser = argparse.ArgumentParser(description="Ingest football-data.org data")
    parser.add_argument(
        "--season",
        default=str(current_year - 1 if date.today().month < 8 else current_year),
        help="Season year start (e.g. 2024 for 2024/25 season)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.season))
