import requests
from PIL import Image

from io import BytesIO
import time

# downloads a single tile
def get_tile(z, x, y):
	# this long url is all official coverage, including trekkers and everything else
	url = f"https://www.google.com/maps/vt?pb=!1m7!8m6!1m3!1i{z}!2i{x}!3i{y}!2i9!3x1!2m8!1e2!2ssvv!4m2!1scc!2s*211m3*211e2*212b1*213e2*212b1*214b1!4m2!1ssvl!2s*211b0*212b1!3m8!2sen!3sus!5e1105!12m4!1e68!2m2!1sset!2sRoadmap!4e0!5m4!1e0!8m2!1e1!1e1!6m6!1e12!2i2!11e0!39b0!44e0!50e0"
	r = requests.get(url)
	r.raise_for_status()
	return r.content

# checks whether an image is empty
def is_empty(image_string):
	buff = BytesIO()
	buff.write(image_string)
	buff.seek(0)
	image = Image.open(buff)
	# blue line layers are always single-band, so this works fine enough
	return image.getextrema()[1] == 0

# gets images from the next layer based on previous layer
def get_next_zoom(zoom_level, prev_coords, save_path = None):
	# checks an image's emptiness and saves it accordingly
	def check_image(coords, nonempty_tmp, retry_tmp):
		try:
			# intenionally avoiding async here to reduce the chances of bot detection & rate limits / ip bans
			# downloading each level takes about 2.5 times more time than the previous one
			# so even level 12 and under is completable in about 8 hours or so on my home computer and mediocre internet
			# could easily be made changed if necessary, but for now, i prefer this "safe" solution since it only needs to run once anyway
			tile_details = get_tile(zoom_level, coords[0], coords[1])
			if not is_empty(tile_details):
				nonempty_tmp.append(coords)
				if save_path:
					with open(f"{save_path}/z{zoom_level}x{coords[0]}y{coords[1]}.png", "wb") as f:
						f.write(tile_details)
		except:
			retry_tmp.append(coords)

	nonempty_coords = []
	retry_coords = []
	for coords in prev_coords:
		for i in range(2):
			for j in range(2):
				new_coords = [2 * coords[0] + i, 2 * coords[1] + j]
				check_image(new_coords, nonempty_coords, retry_coords)
	retry_count = 0
	while len(retry_coords) > 0:
		time.sleep(min(2 ** retry_count, 60))
		retry_count += 1
		new_retry_coords = []
		for coords in retry_coords:
			check_image(coords, nonempty_coords, new_retry_coords)
		retry_coords = new_retry_coords
	return nonempty_coords

if __name__ == "__main__":
	start_time = time.time()
	max_level = 12
	valid_coords = [[0, 0]]
	current_level = 0
	for i in range(1, max_level + 1):
		current_level += 1
		valid_coords = get_next_zoom(current_level, valid_coords, "./tiles")
		current_time = time.time()
		time_diff = round(current_time - start_time, 2)
		print(
			f"Downloaded zoom level {current_level} out of {max_level} in {time_diff} seconds",
			sep = "",
			end = "\r",
			flush = True
		)