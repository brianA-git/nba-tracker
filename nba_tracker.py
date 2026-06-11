# =============================================================================
#  NBA SCORE TRACKER
#  Uses the balldontlie.io free API to fetch live and recent NBA game data.
#  No API key required for basic access (free tier).
#
#  HOW TO RUN:
#    1. Install the requests library (one-time only):
#       pip install requests
#    2. Run the script:
#       python nba_tracker.py
# =============================================================================

import requests
import json
from datetime import datetime, timedelta


# =============================================================================
#  CONFIGURATION
#  Change these values to customize what the tracker shows.
#  BASE_URL is the root of the balldontlie API — all requests start here.
# =============================================================================
BASE_URL   = "https://api.balldontlie.io/v1"
TODAY      = datetime.now().strftime("%Y-%m-%d")
YESTERDAY  = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
SEASON     = 2024   # NBA season year (2024 = the 2024-25 season)
API_KEY    = "faa94368-1879-4ff6-b99e-22f16f51a0fb"


# =============================================================================
#  TERMINAL COLORS
#  These are ANSI escape codes — special character sequences that tell
#  the terminal to display colored text. Not all terminals support them,
#  but VS Code's terminal does.
#  Usage: print(f"{COLORS['green']}Hello{COLORS['reset']}")
# =============================================================================
COLORS = {
    "reset":   "\033[0m",
    "bold":    "\033[1m",
    "dim":     "\033[2m",
    "red":     "\033[91m",
    "green":   "\033[92m",
    "yellow":  "\033[93m",
    "blue":    "\033[94m",
    "magenta": "\033[95m",
    "cyan":    "\033[96m",
    "white":   "\033[97m",
}

def c(color, text):
    """Wrap text in a terminal color. c('green', 'Hello') → colored Hello"""
    return f"{COLORS[color]}{text}{COLORS['reset']}"

def bold(text):
    return f"{COLORS['bold']}{text}{COLORS['reset']}"


# =============================================================================
#  API HELPER — fetch()
#  All API calls go through this single function.
#  It handles errors in one place so we don't repeat try/except everywhere.
#
#  What's happening:
#  - requests.get() sends an HTTP GET request to the URL (like visiting a webpage)
#  - response.json() converts the response text into a Python dictionary
#  - If anything goes wrong, we print a friendly error and return None
# =============================================================================
def fetch(endpoint, params=None):
    url = f"{BASE_URL}/{endpoint}"
    try:
        response = requests.get(url, params=params, timeout=10,
                        headers={"Authorization": API_KEY})
        response.raise_for_status()   # raises an error if status code is 4xx/5xx
        return response.json()
    except requests.exceptions.ConnectionError:
        print(c("red", "  ✗ No internet connection. Check your network."))
        return None
    except requests.exceptions.Timeout:
        print(c("red", "  ✗ Request timed out. Try again."))
        return None
    except requests.exceptions.HTTPError as e:
        print(c("red", f"  ✗ API error: {e}"))
        return None
    except Exception as e:
        print(c("red", f"  ✗ Unexpected error: {e}"))
        return None


# =============================================================================
#  FORMAT HELPERS
#  Small utility functions that format raw data into readable strings.
# =============================================================================

def format_game_status(game):
    """
    Returns a human-readable status string for a game.
    The API returns status as: 'Final', '7:30 pm ET', or a period like '4th Qtr'
    """
    status = game.get("status", "")

    if status == "Final":
        return c("dim", "Final")
    elif "Qtr" in status or "Half" in status or "OT" in status:
        return c("green", f"● LIVE  {status}")
    else:
        # It's an upcoming game — show the tip-off time
        return c("cyan", f"  {status}")


def format_score(game):
    """
    Returns the score line, e.g. '112 - 108'
    Highlights the winning team's score in bold.
    """
    home  = game.get("home_team_score", 0) or 0
    away  = game.get("visitor_team_score", 0) or 0
    status = game.get("status", "")

    if status == "Final" or "Qtr" in status or "Half" in status:
        if home > away:
            return f"{bold(str(home))} - {away}"
        elif away > home:
            return f"{home} - {bold(str(away))}"
        else:
            return f"{home} - {away}"
    else:
        return c("dim", "vs")


def format_team(team):
    """Returns team city + name, e.g. 'Los Angeles Lakers'"""
    return f"{team['city']} {team['name']}"


def format_record(wins, losses):
    """Returns W-L record string"""
    return c("dim", f"({wins}-{losses})")


# =============================================================================
#  FEATURE 1 — Get Today's / Yesterday's Games
#  Fetches all NBA games for a given date and prints a score table.
#  We try today first; if there are no games, we fall back to yesterday.
# =============================================================================
def show_scores(date=None):
    if date is None:
        date = TODAY

    print(f"\n{bold('━━━  NBA SCORES  ━━━')}  {c('dim', date)}\n")

    data = fetch("games", params={
        "dates[]": date,
        "per_page": 15
    })

    if data is None:
        return

    games = data.get("data", [])

    if not games:
        # No games today — try yesterday automatically
        if date == TODAY:
            print(c("dim", "  No games today. Showing yesterday's scores...\n"))
            show_scores(YESTERDAY)
        else:
            print(c("dim", "  No games found for this date."))
        return

    # Print each game as a formatted row
    for game in games:
        home    = game["home_team"]
        visitor = game["visitor_team"]
        status  = format_game_status(game)
        score   = format_score(game)

        home_name    = format_team(home)
        visitor_name = format_team(visitor)

        # Pad team names to consistent width for alignment
        print(f"  {visitor_name:<28} {score:^15}  {home_name:<28}  {status}")

    print()


# =============================================================================
#  FEATURE 2 — Calculated Standings
#  balldontlie.io and TheSportsDB both lock standings behind paid plans.
#  So we calculate them ourselves by fetching all completed games this
#  season and tallying wins/losses per team — exactly how the NBA does it.
#
#  This is Option B: no restrictions, pure logic, great learning exercise.
#  We make multiple paginated API calls to get all ~1200 season games.
# =============================================================================
# Cache for standings — avoids re-fetching if user views standings again
_standings_cache = None

def show_standings():
    global _standings_cache

    print(f"\n{bold('━━━  NBA STANDINGS  ━━━')}  {c('dim', f'{SEASON}-{str(SEASON+1)[-2:]} Season')}\n")

    if _standings_cache is not None:
        east, west = _standings_cache
        print_conferences(east, west)
        return

    print(c("dim", "  Loading recent game results…\n"))

    import time
    all_games = []

    for page in range(1, 4):   # max 3 pages = 300 games
        data = fetch("games", params={
            "seasons[]": SEASON,
            "per_page":  100,
            "page":      page
        })

        if data is None:
            return

        games = data.get("data", [])
        all_games += games

        if len(games) < 100:
            break

        time.sleep(0.8)   # pause between pages

    finished = [g for g in all_games if g.get("status") == "Final"]

    if not finished:
        print(c("dim", "  No completed games found yet this season."))
        return

    records = {}

    for game in finished:
        home    = game["home_team"]
        visitor = game["visitor_team"]
        h_score = game.get("home_team_score") or 0
        v_score = game.get("visitor_team_score") or 0

        if h_score == 0 and v_score == 0:
            continue

        for team in [home, visitor]:
            if team["id"] not in records:
                records[team["id"]] = {
                    "name":       f"{team['city']} {team['name']}",
                    "conference": team.get("conference", ""),
                    "wins":       0,
                    "losses":     0
                }

        if h_score > v_score:
            records[home["id"]]["wins"]      += 1
            records[visitor["id"]]["losses"] += 1
        else:
            records[visitor["id"]]["wins"]   += 1
            records[home["id"]]["losses"]    += 1

    east = sorted(
        [r for r in records.values() if r["conference"] == "East"],
        key=lambda r: r["wins"] / max(r["wins"] + r["losses"], 1),
        reverse=True
    )
    west = sorted(
        [r for r in records.values() if r["conference"] == "West"],
        key=lambda r: r["wins"] / max(r["wins"] + r["losses"], 1),
        reverse=True
    )

    _standings_cache = (east, west)
    print(c("dim", f"  Based on {len(finished)} games  •  cached for this session\n"))
    print_conferences(east, west)


def print_conferences(east, west):
    def print_conf(teams, name, color):
        print(f"  {c(color, bold(f'◆ {name}ern Conference'))}")
        print(f"  {'#':<4} {'Team':<30} {'W':<6} {'L':<6} {'Win%'}")
        print(f"  {c('dim', '─' * 55)}")

        for i, team in enumerate(teams, 1):
            w      = team["wins"]
            l      = team["losses"]
            pct    = f"{w/(w+l):.3f}" if (w+l) > 0 else ".000"
            col    = "white" if i <= 6 else "dim"
            print(f"  {c(col, f'{i}.'):<5} {c(col, team['name']):<30} "
                  f"{c(col, str(w)):<6} {c(col, str(l)):<6} {c(col, pct)}")
        print()

    print_conf(east, "East", "blue")
    print_conf(west, "West", "red")


# =============================================================================
#  FEATURE 3 — Search for a Team's Recent Games
#  Lets the user type a team name and see their last 5 results.
# =============================================================================
def show_team_games(team_name):
    print(f"\n{bold('━━━  TEAM SEARCH  ━━━')}\n")

    # First, find the team ID by searching the teams endpoint
    data = fetch("teams", params={"per_page": 30})

    if data is None:
        return

    teams = data.get("data", [])

    if not teams:
        print(c("yellow", f"  No team found matching '{team_name}'. Try a city or nickname."))
        return

    # Search parameter isn't reliable on free tier — filter manually.
    # Check if the search term appears in the team name, city, or abbreviation.
    query_lower = team_name.lower()
    matched = [
        t for t in teams
        if query_lower in t.get("name", "").lower()
        or query_lower in t.get("city", "").lower()
        or query_lower in t.get("abbreviation", "").lower()
        or query_lower in f"{t.get('city','')} {t.get('name','')}".lower()
    ]

    if not matched:
        print(c("yellow", f"  No team found matching '{team_name}'. Try a city or nickname."))
        print(c("dim",    f"  Try: Lakers, Celtics, Warriors, Heat, OKC, Thunder, Knicks"))
        return

    team = matched[0]
    team_id = team["id"]
    print(f"  Found: {c('cyan', bold(format_team(team)))}  "
          f"{c('dim', team.get('abbreviation',''))}  —  {team.get('conference','')} Conference\n")

    # Now fetch their recent games
    games_data = fetch("games", params={
        "team_ids[]":  team_id,
        "seasons[]":   SEASON,
        "per_page":    8,
    })

    if games_data is None:
        return

    games = games_data.get("data", [])

    # Filter to only completed games and sort by date descending
    finished = [g for g in games if g.get("status") == "Final"]
    finished.sort(key=lambda g: g.get("date", ""), reverse=True)
    recent   = finished[:5]

    if not recent:
        print(c("dim", "  No completed games found yet this season."))
        return

    print(f"  {c('dim', 'Last 5 games:')}\n")
    for game in recent:
        date     = game.get("date", "")[:10]
        home     = game["home_team"]
        visitor  = game["visitor_team"]
        h_score  = game.get("home_team_score", 0)
        v_score  = game.get("visitor_team_score", 0)

        # Was this team the home or away side?
        is_home  = home["id"] == team_id
        opp      = visitor if is_home else home
        our_score  = h_score if is_home else v_score
        opp_score  = v_score if is_home else h_score
        venue      = "vs" if is_home else "@"

        # Win or loss?
        won = our_score > opp_score
        result_str = c("green", "W") if won else c("red", "L")
        score_str  = f"{bold(str(our_score))} - {opp_score}" if won else f"{our_score} - {bold(str(opp_score))}"

        print(f"  {c('dim', date)}  {result_str}  {score_str:<18}  "
              f"{venue} {format_team(opp)}")

    print()


# =============================================================================
#  MAIN MENU
#  The entry point of the script. Shows a simple numbered menu and
#  routes the user's choice to the right function.
# =============================================================================
def print_header():
    print("\n" + c("yellow", bold("  ╔══════════════════════════════╗")))
    print(         c("yellow", bold("  ║     🏀  NBA TRACKER  🏀      ║")))
    print(         c("yellow", bold("  ╚══════════════════════════════╝")))
    print(         c("dim",    f"     Season {SEASON}-{str(SEASON+1)[-2:]}  •  {TODAY}\n"))


def main():
    print_header()

    print(f"  {bold('1.')} Today's scores")
    print(f"  {bold('2.')} League standings")
    print(f"  {bold('3.')} Search a team's recent games")
    print(f"  {bold('4.')} Quit\n")

    while True:
        choice = input(c("cyan", "  Choose an option (1-4): ")).strip()

        if choice == "1":
            show_scores()

        elif choice == "2":
            show_standings()

        elif choice == "3":
            name = input(c("cyan", "\n  Enter team name or city: ")).strip()
            if name:
                show_team_games(name)

        elif choice == "4":
            print(c("dim", "\n  See you on the court. 🏀\n"))
            break

        else:
            print(c("yellow", "  Please enter 1, 2, 3, or 4."))

        # Ask if they want to do something else
        again = input(c("dim", "  Back to menu? (y/n): ")).strip().lower()
        if again != "y":
            print(c("dim", "\n  See you on the court. 🏀\n"))
            break

        print()
        print(f"  {bold('1.')} Today's scores")
        print(f"  {bold('2.')} League standings")
        print(f"  {bold('3.')} Search a team's recent games")
        print(f"  {bold('4.')} Quit\n")


# =============================================================================
#  ENTRY POINT
#  This block only runs when you execute the file directly
#  (python nba_tracker.py), not when it's imported by another script.
#  It's standard Python convention.
# =============================================================================
if __name__ == "__main__":
    main()
