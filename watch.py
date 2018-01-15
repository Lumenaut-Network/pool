import json, requests
from generate import main as start_payout
from stellar_base.horizon import horizon_testnet, horizon_livenet

print("Connecting to horizon-testnet...")

horizon = horizon_testnet()
stream = horizon.operations(sse = True)
INFLATION_TYPE = 9
POOL_ADDRESS = "GA3FUYFOPWZ25YXTCA73RK2UGONHCO27OHQRSGV3VCE67UEPEFEDCOPA"

print("Connected! Watching for inflation operation...")

def investigate_inflation(effects_link):
	res = requests.get(effects_link)
	effects = res.json()["_embedded"]["records"]
	found = False
	for record in effects:
		if record["account"] == POOL_ADDRESS:
			print("Paying out " + record["amount"])
			start_payout(record["amount"])
			found = True
	if not found:
		print("Didn't find account " + POOL_ADDRESS)
		print("Look for yourself: " + effects_linkf)
		
investigate_inflation("https://horizon.stellar.org/operations/66149948126683137/effects")
'''
for response in stream:
	data = json.loads(response.data)
	if type(data) is not dict: continue

	type_i = data["type_i"]
	if type_i == INFLATION_TYPE:
		print("Inflation triggered, investigating...")
		investigate_inflation(data["_links"]["effects"]["href"])
'''	