import sqlite3

con = sqlite3.connect("data.db")
cur = con.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS player_ratings(
	player_id TEXT,
	game_id TEXT,
	ingame_rating INTEGER,
	rating_before INTEGER,
	rating_after INTEGER
)""")
cur.execute("CREATE INDEX rating_at_game ON player_ratings(player_id, game_id)")

cur.execute("""CREATE TABLE IF NOT EXISTS games(
	game_id TEXT PRIMARY KEY NOT NULL,
	map_id TEXT,
	map_name TEXT,
	map_error_distance REAL,
	nmpz INTEGER,
	round_count INTEGER,
	winning_team INTEGER,
	team1_player1 TEXT,
	team1_player2 TEXT,
	team2_player1 TEXT,
	team2_player2 TEXT,
	started_at INTEGER,
	ended_at INTEGER
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS rounds(
	game_id TEXT,
	round_id INTEGER,
	lat REAL,
	lng REAL,
	country_code TEXT,
	heading REAL,
	pitch REAL,
	zoom REAL,
	pano_id TEXT,
	damage INTEGER,
	team1_lat REAL,
	team1_lng REAL,
	team1_distance REAL,
	team1_score INTEGER,
	team2_lat REAL,
	team2_lng REAL,
	team2_distance REAL,
	team2_score INTEGER,
	nearby_intersections INTEGER,
	streetview_coverage INTEGER
)""")
cur.execute("CREATE INDEX round_in_game ON rounds(game_id, round_id)")
cur.execute("CREATE INDEX round_coordinates ON rounds(lat, lng)")