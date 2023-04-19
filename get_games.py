###############################################################################
# This script is only used to get basic game & round info.                    #
# Stuff like ELO reconstruction, getting more details about each round, etc.  #
# is done elsewhere for the sake of clarity.                                  #
# Running this script requires two files: a game_ids.txt file containing the  #
# ids of team duels games (separated by a comma and a space), as well as a    #
# JSON file cookies.json containing your Geoguessr browser cookies.           #
###############################################################################

import requests

import json
import sqlite3

# stringified percent for the progress bar
percent = lambda done, total: str(round(done / total * 100)).rjust(3) + "%"

# flattened 2d list
flatten = lambda l: [x for l2 in l for x in l2]

# converting from geoguessr's weird pano id format to the official one
convert_pano_id = lambda pano: None if not pano else convert_pano_id_raw(pano)
convert_pano_id_raw = lambda pano: "".join(chr(int(pano[i:i+2], 16)) for i in range(0, len(pano), 2))

# get a round by round number
get_round = lambda round_number, rounds: [x for x in rounds if x["roundNumber"] == round_number]

# get data from a single game
def get_game(game_id, cookies):
	base_url = "https://game-server.geoguessr.com/api/duels/"
	url = base_url + game_id
	# get api response
	results = requests.get(url, cookies = cookies)
	results.raise_for_status()
	game = results.json()
	if game["status"] != "Finished" or game["result"]["isDraw"]:
		raise Exception("game has no conclusive results")
	# first, get the game info
	game_info = {}
	# only nm and nmpz exist, so safe to assume that no panning == nmpz
	game_info["nmpz"] = game["movementOptions"]["forbidRotating"]
	# the only relevant game options are about the map, all other settings like multipliers don't matter
	game_info["map_id"] = game["options"]["map"]["slug"]
	game_info["map_name"] = game["options"]["map"]["name"]
	game_info["map_error_distance"] = game["options"]["map"]["maxErrorDistance"]
	# miscellaneous stuff
	game_info["game_id"] = game_id
	game_info["round_count"] = game["currentRoundNumber"]
	# get the relevant players, will be used to reconstruct elo later
	game_info["winning_team"] = int(game["teams"][0]["id"] == game["result"]["winningTeamId"]) + 1
	players = [
		[
			{
				"player_id": player["playerId"],
				"ingame_rating": player["rating"],
				"game_id": game_id
			}
			for player in team["players"]
			if len(player["guesses"]) > 0
		]
		for team in game["teams"]
	]
	# can't clearly identify bot
	if len(players[0]) != 2 or len(players[1]) != 2:
		raise Exception("team has incorrect amount of players")
	game_info["team1_player1"] = players[0][0]["player_id"]
	game_info["team1_player2"] = players[0][1]["player_id"]
	game_info["team2_player1"] = players[1][0]["player_id"]
	game_info["team2_player2"] = players[1][1]["player_id"]
	player_info = flatten(players)
	# now, get the round info
	round_info = []
	for current_round in game["rounds"]:
		current_pano = current_round["panorama"]
		this_round = {}
		this_round["game_id"] = game_id
		this_round["round_id"] = current_round["roundNumber"]
		this_round["lat"] = current_pano["lat"]
		this_round["lng"] = current_pano["lng"]
		this_round["heading"] = current_pano["heading"]
		this_round["pitch"] = current_pano["pitch"]
		this_round["zoom"] = current_pano["zoom"]
		this_round["country_code"] = current_pano["countryCode"]
		this_round["pano_id"] = convert_pano_id(current_pano["panoId"])
		team_rounds = [get_round(current_round["roundNumber"], game["teams"][i]["roundResults"]) for i in range(2)]
		for i in range(2):
			if(len(team_rounds[i]) != 1):
				this_round[f"team{i+1}_lat"] = None
				this_round[f"team{i+1}_lng"] = None
				this_round[f"team{i+1}_distance"] = None
				this_round[f"team{i+1}_score"] = 0
			else:
				team_round = team_rounds[i][0]
				best_guess = team_round["bestGuess"]
				this_round[f"team{i+1}_lat"] = best_guess["lat"]
				this_round[f"team{i+1}_lng"] = best_guess["lng"]
				this_round[f"team{i+1}_distance"] = best_guess["distance"]
				this_round[f"team{i+1}_score"] = team_round["score"]
		this_round["damage"] = abs(this_round["team1_score"] - this_round["team2_score"])
		# geoguessr duels generate rounds in advance, this makes sure that only played rounds are included
		if this_round["team1_lat"] != None or this_round["team2_lat"] != None:
			round_info.append(this_round)
	return [game_info, player_info, round_info]

# inserts a dictionary into an sqlite table, see https://stackoverflow.com/a/36678361
# does not validate anything!
def insert_dictionary(con, table, row):
	cols = ', '.join('"{}"'.format(col) for col in row.keys())
	vals = ', '.join(':{}'.format(col) for col in row.keys())
	sql = 'INSERT INTO "{0}" ({1}) VALUES ({2})'.format(table, cols, vals)
	con.cursor().execute(sql, row)
	con.commit()

def get_all_games():
	# the api doesn't work while logged out
	with open("cookies.json") as f:
		cookies = json.load(f)
	with open("game_ids.txt") as f:
		game_ids = f.read().split(", ")
	con = sqlite3.connect("data.db")
	game_count = len(game_ids)
	print(f"Collecting data from {game_count} games")
	parsed_count = 0
	success_count = 0
	for game_id in game_ids:
		parsed_count += 1
		try:
			game_info, player_info, round_info = get_game(game_id, cookies)
			insert_dictionary(con, "games", game_info)
			for player in player_info:
				insert_dictionary(con, "player_ratings", player)
			for current_round in round_info:
				insert_dictionary(con, "rounds", current_round)
			success_count += 1
		except:
			# if we failed to decode, we can just skip, a few missing data points are fine
			pass
		# keep a progress indicator in the terminal
		print(
			f"({percent(parsed_count, game_count)}) Parsed {parsed_count} games ({success_count} successful)",
			sep = "",
			end = "\r",
			flush = True
		)

if __name__ == "__main__":
	get_all_games()