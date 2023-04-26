import numpy as np
from PIL import Image

import math
import os.path
import sys
import sqlite3

class ScoreCalculator:
	def __init__(self, cache_tile_scores = True, zoom = 12):
		self.cache_tile_scores = cache_tile_scores
		self.tile_scores = {}
		self.zoom = zoom

	# gets a tile from coordinates
	# adapted from here: https://developers.google.com/maps/documentation/javascript/examples/map-coordinates
	def get_tile_from_coords(self, coords):
		lat = coords["lat"]
		lng = coords["lng"]
		scale = 1 << self.zoom
		# remove -1 and +1 since mercator projection would put them to infinity
		sin_y = min(max(math.sin(lat * math.pi / 180), -0.9999), 0.9999)
		return {
			"x": math.floor(scale * (0.5 + lng / 360)),
			"y": math.floor(scale * (0.5 - math.log((1 + sin_y)  / (1 - sin_y)) / (4 * math.pi)))
		}

	# gets lat, lng from mercator coordinates (assumes a tile size of 1)
	# could probably be more elegant, but i just solved for lat and lng in the previous equations
	def get_corner_from_tile(self, tile):
		x = tile["x"]
		y = tile["y"]
		scale = 1 << self.zoom
		temp_exp = math.exp((0.5 - y / scale) * 4 * math.pi)
		sin_y = (temp_exp - 1) / (temp_exp + 1)
		return {
			"lat": 180 / math.pi * math.asin(sin_y),
			"lng": 360 * (x / scale - 0.5)
		}

	# gets the coordinate boundaries from a tile
	def get_bounds_from_tile(self, tile):
		x = tile["x"]
		y = tile["y"]
		scale = 1 << self.zoom
		northwest = {
			"x": x,
			"y": y
		}
		southeast = {
			"x": x + 1,
			"y": y + 1
		}
		northwest_coords = self.get_corner_from_tile(northwest)
		southeast_coords = self.get_corner_from_tile(southeast)
		return {
			"lat_min": southeast_coords["lat"],
			"lat_max": northwest_coords["lat"],
			"lng_min": northwest_coords["lng"],
			"lng_max": southeast_coords["lng"]
		}



	# gets the score of an individual tile
	# does NOT adjust for area
	def tile_score(self, tile, tile_path = "./tiles"):
		# caching to save computation time in exchange for memory
		x = tile["x"]
		y = tile["y"]
		if self.cache_tile_scores:
			tile_tuple = (x, y)
			if tile_tuple in self.tile_scores:
				return self.tile_scores[tile_tuple]
		tile_name = f"{tile_path}/z{self.zoom}x{x}y{y}.png"
		if not os.path.isfile(tile_name):
			return 0
		image = Image.open(tile_name)
		palette_raw = image.getpalette()
		colours = [palette_raw[i:i+3] for i in range(0, len(palette_raw), 3)]
		# these roughly correspond to most of the non-bright colours. can be imperfect (too lenient), but usually fine enough
		acceptable_indices = [i for i in range(len(colours)) if 100 > colours[i][0] > 0]
		acceptable_indices.sort()
		acceptable_indices_np = np.array(acceptable_indices)
		image_np = np.array(image)
		# fastest way i could find to the number of elements that are in a different array
		raw_score = np.count_nonzero(np.searchsorted(acceptable_indices_np, image_np))
		if self.cache_tile_scores:
			self.tile_scores[tile_tuple] = raw_score
		return raw_score

	# gets a distance from a coordinate to a tile
	# it has some imperfections, such as assuming a spherical earth, and using slightly simplified heuristics for finding nearest point
	# overall error shouldn't be too much, so using these simplified heuristics is worth it
	def distance_to_tile(self, coords, tile):
		lat = coords["lat"]
		lng = coords["lng"]
		tile_bounds = self.get_bounds_from_tile(tile)
		# gets corners if the tiles don't align, and the exact same lat/lng if they do, for the sake of simplicity
		if tile_bounds["lat_min"] > lat:
			selected_lat = tile_bounds["lat_min"]
		elif tile_bounds["lat_max"] < lat:
			selected_lat = tile_bounds["lat_max"]
		else:
			selected_lat = lat
		if tile_bounds["lng_min"] > lng:
			selected_lng = tile_bounds["lng_min"]
		elif tile_bounds["lng_max"] < lng:
			selected_lng = tile_bounds["lng_max"]
		else:
			selected_lng = lng
		d_lat = math.radians(lat - selected_lat)
		d_lng = math.radians(lng - selected_lng)
		a = math.sin(d_lat / 2) ** 2 + math.cos(lat) * math.cos(selected_lat) * math.sin(d_lng / 2) ** 2
		return 2 * math.asin(math.sqrt(a)) * 6371


	# gets the score of a given coordinate
	# the core idea is to first sum up nearby tiles, with weights given based on the distance to the coordinates
	# then adjust the weights to total up to 1
	# this is not the perfect measurement since around the equator, tiles cover a larger area, so a larger distance is included
	# but it's decent enough for all intents and purposes as weighting by area is generally unwise
	# returns 0 for no coverage and 10000 for impossibly dense coverage
	def coordinate_score(self, coords):
		scores = []
		base_tile = self.get_tile_from_coords(coords)
		tile = base_tile
		# always get up to zoom level tiles away to account for coverage up to 50km or so
		for total_distance in range(self.zoom):
			for i in range(-total_distance, total_distance + 1):
				# getting the tiles in both directions
				j = total_distance - abs(i)
				if j == 0:
					tiles = [{"x": base_tile["x"] + i, "y": base_tile["y"]}]
				else:
					tiles = [
						{"x": base_tile["x"] + i, "y": base_tile["y"] - j},
						{"x": base_tile["x"] + i, "y": base_tile["y"] + j}
					]
				for tile in tiles:
					distance = self.distance_to_tile(coords, tile)
					# ensures that nearest tile has a distance of 0
					# and has 10km as 1/4
					weight = (10 / (10 + distance))
					score = self.tile_score(tile)
					scores.append({
						"score":  score * (weight ** 2),
						"weight": weight ** 2
					})
		# to ensure that having nearby sea doesn't mess with the data, remove the 2/3 lowest-scoring tiles
		scores.sort(key = lambda x: x["score"], reverse = True)
		scores = scores[ : math.ceil(len(scores) / 3)]
		return round(sum(x["score"] for x in scores) / sum(x["weight"] for x in scores) * 10000 / (1 << 16))

if __name__ == "__main__":
	score_calculator = ScoreCalculator()
	con = sqlite3.connect("data.db")
	cur = con.cursor()
	cur.execute("SELECT lat, lng FROM rounds GROUP BY lat, lng")
	locations = cur.fetchall()
	location_count = len(locations)
	calculated_count = 0
	print(f"Getting coverage density for {location_count} locations")
	for location in locations:
		calculated_count += 1
		(lat, lng) = location
		score = score_calculator.coordinate_score({"lat": lat, "lng": lng})
		cur.execute("UPDATE rounds SET streetview_coverage = ? WHERE lat = ? AND lng = ?", (score, lat, lng))
		if calculated_count % 10000 == 0:
			con.commit()
		print(
			f"Calculated {calculated_count} scores out of {location_count}",
			sep = "",
			end = "\r",
			flush = True
		)