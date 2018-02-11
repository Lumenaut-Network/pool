import logging
import time
import sys
import os

logDir = "./logs"
if not os.path.exists(logDir):
    os.makedirs(logDir)

logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

fileHandler =logging.FileHandler("{0}/{1}.log".format(logDir, "main"))
fileHandler.setFormatter(logFormatter)
logger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)

import json
import requests
from generate import main as start_payout
from stellar_base.horizon import horizon_testnet

# print("Connecting to horizon-testnet...")
logger.info("Connecting to horizon-testnet...")

# GA7QE55JGHFT5OKB2WKFFVKAPLQSEAWILETXT63QA56HHU6PLZBOOOOO SBO3GNKMDNN5GUE6Z6AODW4UEZXGIRLMXRA4SBL2O2PPBO4UZOPDBJSY  # noqa
horizon = horizon_testnet()
stream = horizon.operations(sse=True)
INFLATION_TYPE = 9
POOL_ADDRESS = "GCFXD4OBX4TZ5GGBWIXLIJHTU2Z6OWVPYYU44QSKCCU7P2RGFOOHTEST"

logger.info("Connected! Watching for inflation operation...")

def investigate_inflation(effects_link):
	res = requests.get(effects_link)
	effects = res.json()["_embedded"]["records"]
	found = False
	for record in effects:
		if record["account"] == POOL_ADDRESS:
			logger.info("Paying out " + record["amount"])
			start_payout(record["amount"])
			found = True
	if not found:
		logger.info("Didn't find account " + POOL_ADDRESS)
		logger.info("Look for yourself: " + effects_link)

for response in stream:
	data = json.loads(response.data)
	if type(data) is not dict:
		continue

	type_i = data["type_i"]
	if type_i == INFLATION_TYPE:
		logger.info("Inflation triggered, investigating...")
