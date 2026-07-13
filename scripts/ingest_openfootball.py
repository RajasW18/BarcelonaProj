"""
ingest_openfootball.py
─────────────────────
Parses fixture files from the openfootball/espana repository and
upserts match data into the PostgreSQL database.

Usage:
    python scripts/ingest_openfootball.py --seasons-dir /path/to/espana/repo

The openfootball text format looks like:

    [Matchday 1]
    24.08.2024  FC Barcelona  2-1  Real Madrid
    24.08.2024  Atlético      1-0  Sevilla

Lines starting with '[' are matchday headers.
Fixture lines follow: date  home_team  score  away_team
"""
import argparse
import asyncio
import re
import sys
from pathlib import Path

import asyncpg

# Add project root to path so we can import api/
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.config import settings


# ─── Regex patterns ───────────────────────────────────────────────────────────
MATCHDAY_RE = re.compile(r"^\[(?:Matchday|Round|Spieltag)\s+(\d+)\]", re.IGNORECASE)
# Date  Home  Score  Away  [optional extra]
FIXTURE_RE = re.compile(
    r"^(\d{2}\.\d{2}\.\d{4})\s+"     # date  DD.MM.YYYY
    r"(.+?)\s+"                         # home team
    r"(\d+)-(\d+)\s+"                  # score N-N
    r"(.+?)$"                           # away team
)


def parse_date(date_str: str):
    """Convert DD.MM.YYYY → Python date."""
    from datetime import datetime
    return datetime.strptime(date_str, "%d.%m.%Y").date()


def normalize_team_name(name: str) -> str:
    """Strip trailing/leading whitespace and common abbreviation noise."""
    return name.strip()


async def get_or_create_team(conn: asyncpg.Connection, name: str) -> int:
    """Return existing team id, or insert and return new id."""
    row = await conn.fetchrow("SELECT id FROM teams WHERE name = $1", name)
    if row:
        return row["id"]
    return await conn.fetchval(
        "INSERT INTO teams(name) VALUES($1) RETURNING id", name
    )


async def get_or_create_competition(
    conn: asyncpg.Connection, name: str, season: str
) -> int:
    row = await conn.fetchrow(
        "SELECT id FROM competitions WHERE name = $1 AND season = $2", name, season
    )
    if row:
        return row["id"]
    return await conn.fetchval(
        "INSERT INTO competitions(name, season, code) VALUES($1, $2, 'PD') RETURNING id",
        name,
        season,
    )


async def ingest_file(
    conn: asyncpg.Connection,
    filepath: Path,
    competition_name: str,
    season: str,
) -> int:
    comp_id = await get_or_create_competition(conn, competition_name, season)
    current_matchday = None
    inserted = 0

    with open(filepath, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            md_match = MATCHDAY_RE.match(line)
            if md_match:
                current_matchday = int(md_match.group(1))
                continue

            fix_match = FIXTURE_RE.match(line)
            if fix_match and current_matchday is not None:
                date_str, home_raw, home_goals, away_goals, away_raw = fix_match.groups()
                home_name = normalize_team_name(home_raw)
                away_name = normalize_team_name(away_raw)

                home_id = await get_or_create_team(conn, home_name)
                away_id = await get_or_create_team(conn, away_name)
                match_date = parse_date(date_str)

                await conn.execute(
                    """
                    INSERT INTO matches
                        (competition_id, season, matchday, match_date,
                         home_team_id, away_team_id, home_score, away_score,
                         status, source)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'FINISHED','openfootball')
                    ON CONFLICT DO NOTHING
                    """,
                    comp_id,
                    season,
                    current_matchday,
                    match_date,
                    home_id,
                    away_id,
                    int(home_goals),
                    int(away_goals),
                )
                inserted += 1

    return inserted


async def main(seasons_dir: Path):
    pool = await asyncpg.create_pool(dsn=settings.database_url)

    total = 0
    # Walk the directory looking for season fixture files
    for filepath in sorted(seasons_dir.glob("**/*.txt")):
        # Try to determine season from directory name, e.g. "2024-25"
        parts = filepath.parts
        season = "Unknown"
        for part in parts:
            if re.match(r"\d{4}-\d{2}", part):
                year_start = int(part[:4])
                year_end = year_start + 1
                season = f"{year_start}/{str(year_end)[-2:]}"
                break

        competition_name = "La Liga"
        if "copa" in filepath.name.lower():
            competition_name = "Copa del Rey"
        elif "champions" in filepath.name.lower() or "cl" in filepath.name.lower():
            competition_name = "UEFA Champions League"

        print(f"  Ingesting {filepath.name} [{season}] …", end=" ")
        async with pool.acquire() as conn:
            count = await ingest_file(conn, filepath, competition_name, season)
        print(f"{count} fixtures")
        total += count

    await pool.close()
    print(f"\n✅ Total fixtures ingested: {total}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest openfootball/espana data")
    parser.add_argument(
        "--seasons-dir",
        required=True,
        help="Path to the cloned openfootball/espana repository root",
    )
    args = parser.parse_args()

    asyncio.run(main(Path(args.seasons_dir)))
