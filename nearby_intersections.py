import requests

import sqlite3
import random
import sys

# stringified percent for the progress bar
percent = lambda done, total: str(round(done / total * 100)).rjust(3) + "%"

# gets the number of intersections in osm for a singular location
def get_intersection_count(lat, lng, distance = 500, endpoint = "https://overpass.kumi.systems/api/interpreter"):
	query = f"""
	[out:json];
	way(around:{distance},{lat},{lng})[highway~"^(motorway|trunk|primary|secondary|tertiary|residential)$"] -> .nearbyRoads;
	foreach.nearbyRoads -> .road(
		(.nearbyRoads; - .road;) -> .otherRoads;
		node(w.road) -> .roadNodes;
		node(w.otherRoads) -> .otherRoadNodes;
		node.roadNodes.otherRoadNodes;
		out;
 	);
 	"""
	r = requests.post(endpoint, data = query)
	r.raise_for_status()
	response = r.json()
	return len(response["elements"])

# gets the number of intersections in osm for all locations (or n locations, for testing)
def get_all_intersection_counts(limit = sys.maxsize):
	# weights determined based on usage policy & server resources
	possible_endpoints = [
		{"url": "https://overpass-api.de/api/interpreter", "weight": 4},
		{"url": "https://maps.mail.ru/osm/tools/overpass/api/interpreter", "weight": 20},
		{"url": "https://overpass.openstreetmap.ru/api/interpreter", "weight": 1},
		{"url": "https://overpass.kumi.systems/api/interpreter", "weight": 10}
	]
	# this is a very ugly solution, but since the weights our small, it works fine
	weight_indices = []
	i = 0
	for endpoint in possible_endpoints:
		weight_indices.extend([i] * endpoint["weight"])
		i += 1
	total_weight = len(weight_indices)
	con = sqlite3.connect("data.db")
	cur = con.cursor()
	cur.execute("SELECT lat, lng FROM rounds WHERE nearby_intersections IS NULL GROUP BY lat, lng")
	locations = cur.fetchall()
	intersections_for = min(len(locations), limit)
	print(f"Getting intersection counts for {intersections_for} locations")
	parsed_count = 0
	success_count = 0
	for location in locations:
		parsed_count += 1
		(lat, lng) = location
		try:
			endpoint_index = random.randint(0, total_weight - 1)
			# randomising endpoints to not get timed out
			intersection_count = get_intersection_count(lat, lng, endpoint = possible_endpoints[weight_indices[endpoint_index]]["url"])
			cur.execute("UPDATE rounds SET nearby_intersections = ? WHERE lat = ? AND lng = ?", (intersection_count, lat, lng))
			con.commit()
			success_count += 1
			print(
				f"({percent(parsed_count, intersections_for)}) Parsed {parsed_count} coordinates ({success_count} successful)",
				sep = "",
				end = "\r",
				flush = True
			)
		except:
			# nothing happened, we can just try again later / at a different endpoint
			pass
		if parsed_count >= limit:
			break

if __name__ == "__main__":
	# using small limits since many overpass instances don't provide data about their rate limits
	# could just use a timeout inbetween queries, but that can be over-cautious
	# so manually running and keeping an eye on error-rates is what i've found to be the most reliable
	get_all_intersection_counts(10000)