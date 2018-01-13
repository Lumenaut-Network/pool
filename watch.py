import json
from calculate import main as start_payout
from stellar_base.horizon import horizon_testnet, horizon_livenet

print("Connecting to horizon-testnet...")

horizon = horizon_testnet()
stream = horizon.operations(sse = True)
INFLATION_TYPE = 9

print("Connected! Watching for inflation operation...")

for response in stream:
	data = json.loads(response.data)
	if type(data) is not dict: continue

	type_i = data["type_i"]
	if type_i == INFLATION_TYPE:
		print("Inflation triggered, starting payout...")
		start_payout()