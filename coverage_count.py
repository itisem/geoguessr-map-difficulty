import aiohttp

import asyncio
import sqlite3

# gets the number of panos for a single location
async def coverage_count(session, location, radius = 10):
	url = "https://maps.googleapis.com/$rpc/google.internal.maps.mapsjs.v1.MapsJsInternalService/SingleImageSearch"
	# this is complicated protobuf data. since there is only one field that i need to change, i will not write ful protobuf definitions, and instead, just adjust the data as necessary
	request_data = f'[["apiv3",null,null,null,"US",null,null,null,null,null,[[false]]],[[null,null,{location["lat"]},{location["lng"]}],{radius}],[null,["en","GB"],null,null,null,null,null,null,[2],null,[[[2,true,2],[3,true,2],[10,true,2]]]],[[1,2,3,4,8,6]]]'
	headers = {"content-type": "application/json+protobuf; charset=UTF-8"}
	response = await session.post(url, data = request_data, headers = headers)
	contents = await response.json()
	# only one field == error
	if(len(contents) <= 1):
		count = 0
	else:
		# [1][5][0][8] contains the linked dates
		try:
			if(contents[1][5][0][8]):
				# getting pano id's to remove unofficial panos
				linked_dates = contents[1][5][0][8]
				linked_panos = contents[1][5][0][3][0]
				# all official panos have an id length of 22, and no unofficial ones do
				linked_details = [{"date": x[1], "pano": linked_panos[x[0]][0][1]} for x in linked_dates]
				linked_details = [x for x in linked_details if len(x["pano"]) == 22]
				count = 1 + len(linked_details)
			else:
				count = 1
		except:
			# it will fail iff linked_dates is undefined, in which case the total number of panos is 1
			count = 1
	return {"lat": location["lat"], "lng": location["lng"], "count": count}

# counts the number of locations in a list of locations
async def coverage_count_chunk(session, locations, radius = 10):
	tasks = []
	for location in locations:
		tasks.append(coverage_count(session, location))
	responses = await asyncio.gather(*tasks)
	return responses

# chunks an array into pieces
def chunk(locations, chunk_size = 500):
	for i in range(0, len(locations), chunk_size):
		yield locations[i : i + chunk_size]

# gets coverage counts for all locations
async def get_all_coverage(chunk_size = 500, radius = 10):
	con = sqlite3.connect("data.db")
	cur = con.cursor()
	cur.execute("SELECT lat, lng FROM rounds WHERE coverage_dates IS NULL GROUP BY lat, lng")
	coords = cur.fetchall()
	coords = [{"lat": x[0], "lng": x[1]} for x in coords]
	total_coords = len(coords)
	i = 0
	async with aiohttp.ClientSession() as session:
		for locations in chunk(coords, chunk_size):
			i += chunk_size
			results = await coverage_count_chunk(session, locations, radius)
			for result in results:
				cur.execute("UPDATE rounds SET coverage_dates = ? WHERE lat = ? AND lng = ?", (result["count"], result["lat"], result["lng"]))
			con.commit()
			print(
			f"Got counts for {i} out of {total_coords}",
			sep = "",
			end = "\r",
			flush = True
		)


if __name__ == "__main__":
	asyncio.run(get_all_coverage())