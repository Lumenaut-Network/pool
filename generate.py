import logging
import time
import sys
import sqlite3
import json
import base64

from decimal import Decimal, ROUND_DOWN, InvalidOperation

from stellar_base.asset import Asset
from stellar_base.operation import Payment
from stellar_base.transaction import Transaction
from stellar_base.transaction_envelope import TransactionEnvelope as Te
from stellar_base.horizon import horizon_testnet

logger = logging.getLogger("payout")

logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] \
[%(levelname)-5.5s]  %(message)s")

logger.setLevel(logging.DEBUG)

fileHandler = logging.FileHandler("{0}/{1}.log".format(
	"./logs",
	time.strftime("%Y%m%d-%H%M%S")))

fileHandler.setFormatter(logFormatter)
logger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)


pool_address = "GCFXD4OBX4TZ5GGBWIXLIJHTU2Z6OWVPYYU44QSKCCU7P2RGFOOHTEST"

db_address = "../core/stellar.db"
select_donations_op = """
	SELECT * FROM accountdata WHERE
	`dataname` LIKE 'Lumenaut.net donation%'"""

select_accounts_op = """
	SELECT `accounts`.`accountid`, `balance` FROM `accounts`
	WHERE `inflationdest`='%s'""" % pool_address

network = "TESTNET"
horizon = horizon_testnet()

BASE_FEE = 100
XLM_STROOP = 10000000
XLM_FEE = Decimal(BASE_FEE / XLM_STROOP)

donation_payouts = {}


def XLM_Decimal(n):
	# 7 decimal places is the longest supported
	return Decimal(n).quantize(Decimal('.0000001'), rounding=ROUND_DOWN)


def parse_donation(donation_data):
	donation_data = base64.b64decode(donation_data).decode("utf-8")

	# Get the donation percentage and destination address from the
	# base64 data string
	try:
		pct, address = donation_data.split("%")
		pct = Decimal(pct)
		if pct < 0 or pct > 100 or len(address) != 56 or address[0] != 'G':
			return None
		else:
			return (address, pct / 100)
	except ValueError:
		# Split didn't produce two elements (no '%' char in the donation_string)
		return None
	except InvalidOperation:
		# XLM_Decimal() can't produce a valid value (malformed string)
		return None


def accounts_payouts(conn, pool_addr, inflation, size=100):
	cur = conn.cursor()
	cur.execute("SELECT Sum(balance) FROM accounts \
	WHERE `inflationdest`=?", (pool_address,))

	total_balance = XLM_Decimal(cur.fetchone()[0])

	logger.debug("Total Balance: %(total_balance)s")
	logger.debug("Inflation: %(inflation)s")

	cur.execute(select_donations_op)

	donations = {}
	for row in cur:
		donor = row[0]
		donation = parse_donation(row[2])

		if donation is not None:
			donation_address, percentage = donation

			if donor not in donations:
				donations[donor] = {}
			donations[donor][donation_address] = percentage

	payouts = []
	batch = []

	cur.execute(select_accounts_op)
	for row in cur:
		accountid = row[0]
		account_balance = XLM_Decimal(row[1])
		account_inflation = (account_balance / total_balance) * inflation

		if accountid in donations:
			inflation_sub = 0

			for address in donations[accountid]:
				pct = donations[accountid][address]
				donation_amt = account_inflation * pct
				donation_payouts[address] = XLM_Decimal(
					donation_payouts.get(address, 0) + donation_amt)
				# take the transaction fee from donations
				# (even though they will be bundled)
				inflation_sub += donation_amt + XLM_FEE

			account_inflation -= inflation_sub

		logger.debug("Created batch %(accountid)s | \
		balance: %(account_balance)s | \
		inflation: %(account_inflation)s")

		batch.append((accountid, XLM_Decimal(account_inflation - XLM_FEE)))

		if len(batch) >= 100:
			payouts.append(batch)
			batch = []

	for address in donation_payouts:
		batch.append((address, donation_payouts[address]))

		if len(batch) >= 100:
			payouts.append(batch)
			batch = []

	if len(batch) > 0:
		payouts.append(batch)
		batch = []

	return payouts


def make_payment_op(account_id, amount):
	return Payment({
		'destination': account_id,
		'amount': str(amount),
		'asset': Asset('XLM')
	})


def main(inflation):
	# TODO: Let user select the connection type
	# The stellar/quickstart Docker image uses PostgreSQL

	logger.debug("Connecting to database...")
	conn = sqlite3.connect(db_address)
	logger.debug("Connected!")

	logger.debug("Getting the next transaction sequence number...")
	sequence = horizon.account(pool_address).get('sequence')
	logger.debug("Done! - Transaction Sequence: %(sequence)s")

	inflation = XLM_Decimal(inflation)
	transactions = []
	total_payments_cost = 0
	num_payments = 0
	total_fee_cost = 0

	logger.debug("Processing account batches...")
	# Create one transaction for each batch
	for batch in accounts_payouts(conn, pool_address, inflation):
		logger.debug("\tProcessing %(batch.aid)s with %(batch.amount)s")

		op_count = 0
		ops = {'sequence': sequence, 'operations': []}
		for aid, amount in batch:
			# Include payment operation on ops{}
			paymentOp = make_payment_op(aid, amount)

			logger.debug("\t\t\Created Payment %(paymentOp)s")
			ops['operations'].append(paymentOp)
			op_count += 1

		logger.debug("\t\tBuilding Transaction...")
		tx = Transaction(
			source=pool_address,
			opts=ops
		)
		tx.fee = op_count * BASE_FEE
		envelope = Te(tx=tx, opts={"network_id": network})
		# Append the transaction plain-text (JSON) on the list
		transaction = envelope.xdr().decode("utf-8")
		logger.debug("\t\tTransaction Created")
		logger.debug("\t\t%(transaction)s")

		transactions.append(transaction)

		# Calculate stats
		total_fee_cost += XLM_Decimal(tx.fee) / XLM_STROOP
		total_payments_cost += sum([
			XLM_Decimal(payment.amount) for payment in tx.operations])
		num_payments += len(tx.operations)

		# Prepare the next sequence number for the transactions
		sequence = int(sequence) + 1

	logger.info((
		"Stats: \n"
		"\tInflation received: %s\n"
		"\tA total of %s XLM paid over %s inflation payments "
		"using %s XLM in fees. \n"
		"\tNumber of unique donation addresses: %s\n") % (
			inflation,
			total_payments_cost,
			num_payments,
			total_fee_cost,
			len(donation_payouts),))

	with open("transactions.json", 'w') as outf:
		json.dump(transactions, outf)
	logger.info("Output to transactions.json")


TEST_AMT = 49855.2650163
if __name__ == '__main__':
	main(TEST_AMT)
