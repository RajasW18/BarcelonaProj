"""
sql_query tool — allows the agent to run safe, read-only SELECT queries
against the FC Barcelona football database.

Schema reference:
  teams, players, competitions, matches, standings, player_stats
"""
import json
from agents import function_tool
from api.db.connection import get_pool


@function_tool
async def sql_query(sql: str) -> str:
    """
    Execute a read-only SQL SELECT query against the FC Barcelona football
    database. Use this tool for factual, structured questions such as:
    - Match results and scorelines
    - La Liga or Champions League standings / table
    - Player statistics (goals, assists, appearances, cards)
    - Upcoming or historical fixtures
    - Squad list and player info

    Available tables:
      - teams(id, api_id, name, short_name, tla, crest_url, founded, venue)
      - players(id, api_id, team_id, name, first_name, last_name, position,
                nationality, date_of_birth, shirt_number)
      - competitions(id, api_id, code, name, area, season)
      - matches(id, competition_id, season, matchday, match_date,
                home_team_id, away_team_id, home_score, away_score, status, stage)
      - standings(competition_id, season, team_id, position, played_games,
                  won, draw, lost, goals_for, goals_against, goal_difference, points, form)
      - player_stats(player_id, competition_id, season, goals, assists,
                     appearances, minutes_played, yellow_cards, red_cards)

    FC Barcelona's team id is 81 (football-data.org).
    La Liga competition code is 'PD'.

    CRITICAL RULES:
    1. ONLY use the EXACT table names listed above. DO NOT use made-up tables like 'la_liga_standings' or 'la_liga_table'.
    2. ONLY use SELECT statements — no INSERT, UPDATE, DELETE, DROP.
    3. The standings table DOES NOT have a team name column. You MUST join: `standings JOIN teams ON standings.team_id = teams.id`.
    4. Limit large result sets with LIMIT 20 unless the user asks for more.

    Example Query for Standings:
    SELECT s.position, t.name, s.points, s.played_games, s.won, s.draw, s.lost 
    FROM standings s JOIN teams t ON s.team_id = t.id 
    ORDER BY s.position ASC;
    """
    stripped = sql.strip()
    if not stripped.upper().startswith("SELECT"):
        return json.dumps({"error": "Only SELECT queries are permitted."})

    # Disallow any mutation keywords (defense-in-depth)
    forbidden = {"INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE"}
    upper_sql = stripped.upper()
    if any(kw in upper_sql for kw in forbidden):
        return json.dumps({"error": "Mutation statements are not allowed."})

    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            rows = await conn.fetch(stripped, timeout=15)
            result = [dict(r) for r in rows[:50]]
            return json.dumps(result, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc)})
