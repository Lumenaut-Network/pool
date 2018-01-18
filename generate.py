import sqlite3
import psycopg2
import json
import base64

from decimal import Decimal, ROUND_DOWN, InvalidOperation

from stellar_base.asset import Asset
from stellar_base.memo import TextMemo
from stellar_base.operation import Payment
from stellar_base.transaction import Transaction
from stellar_base.transaction_envelope import TransactionEnvelope as Te
from stellar_base.horizon import horizon_testnet
from stellar_base.utils import AccountNotExistError

pool_address = "GCFXD4OBX4TZ5GGBWIXLIJHTU2Z6OWVPYYU44QSKCCU7P2RGFOOHTEST"
network = "TESTNET"
horizon = horizon_testnet()

#db_address = "../core/stellar.db"
select_total_votes = "SELECT Sum(balance) FROM accounts WHERE `inflationdest`=?"
select_account_op = """
	SELECT `accounts`.`accountid`, `balance`, `datavalue` FROM `accounts`
	LEFT JOIN `accountdata`
		ON `accountdata`.`accountid` = `accounts`.`accountid`
		AND `dataname`='lumenaut.net donation'
	WHERE `inflationdest`=?"""

db_address = "dbname='core' user='stellar' host='localhost' password='testdb'"
psql_total_votes = "SELECT SUM(balance) FROM accounts WHERE inflationdest = %s"
psql_account_op = """
	SELECT accounts.accountid, balance, datavalue FROM accounts
	LEFT JOIN accountdata
		ON accountdata.accountid = accounts.accountid
		AND dataname LIKE 'lumenaut.net%%'
	WHERE inflationdest = %s"""

BASE_FEE = 100
XLM_STROOP = 10000000
VOTES_ORG = 0
VOTES_NOW = 1

# Voters is a dictionary that maps IDs to how many votes they have
# (before and after the donations)
voters = {}
# Donors is a dictionary that maps IDs to a list of donation_data
# (number%address string encoded in base64)
donors = {}


def XLM_Decimal(n):
	# 7 decimal places is the longest supported
	return Decimal(n).quantize(Decimal('.0000001'), rounding=ROUND_DOWN)


def donate_votes(donor_id, donation_data):
	donation_data = base64.b64decode(donation_data).decode("utf-8")
	# Get the donation percentage and destination address from the
	# base64 data string
	try:
		pct, donee_address = donation_data.split("%")
		pct = XLM_Decimal(pct) / 100
		if pct < 0 or pct > 1:  # Accept only [0,1]
			return
	except ValueError:
		# Split didn't produce two elements (no '%' char in the donation_string)
		return
	except InvalidOperation:
		# XLM_Decimal() can't produce a valid value (malformed string)
		return

	# Percentage is a valid number. If donor still has votes, donate
	if voters[donor_id][VOTES_NOW] >= 0:
		# To calculate the value to donate, we use the donor's original balance
		amt = XLM_Decimal(voters[donor_id][VOTES_ORG] * pct)
		voters[donor_id][VOTES_NOW] -= amt
		# If donee is a 'new voter', set both values (but change only the second)
		if donee_address in voters.keys():
			voters[donee_address][VOTES_NOW] += amt
		else:
			voters[donee_address] = [amt, amt]

def accounts_payouts(conn, pool_addr, inflation, size=100):
	# Extract the sum of all votes from the DB
	cur = conn.cursor()
	#cur.execute(select_total_votes, (pool_address, ))
	cur.execute(psql_total_votes, (pool_address, ))
	total_votes = Decimal(cur.fetchone()[0]) / XLM_STROOP

	# Extract Addresses, votes and donation lists for each voter from the DB
	#cur.execute(select_account_op, (pool_addr, ))
	cur.execute(psql_account_op, (pool_addr, ))
	while True:
		batch = cur.fetchmany(size)
		if not batch or batch == ():
			break
		# Populate the dictionaries of voters and donors
		for aid, balance, donation_data in batch:
			if aid not in voters.keys():
				votes = Decimal(balance) / XLM_STROOP
				# Add twice because we want the value before and after the donations
				voters[aid] = [votes, votes]
			if donation_data:
				if aid not in donors.keys():
					donors[aid] = [donation_data]
				else:
					donors[aid].append(donation_data)

	# Each donor may have one or more donation_data
	for aid in donors.keys():
		for donation_data in donors[aid]:
			donate_votes(aid, donation_data)

	# Now voters[address][VOTES_NOW] holds the correct values for every voter.
	# Calculate payouts in a list of batches, each containing 'size' (default=100)
	payouts = []
	batch = []
	for aid, votes in voters.items():
		# Make sure not to create payouts with zero or negative values
		if votes[VOTES_NOW] <= XLM_Decimal(BASE_FEE / XLM_STROOP):
			continue
		# Make sure the pool does not create a payout to itself
		if aid == pool_addr:
			continue
		# Calculate the payout for this voter: inflation * (votes / total_votes)
		pay_pct = votes[VOTES_NOW] / total_votes
		pay = XLM_Decimal(inflation * pay_pct)
		# Add payout to the batch (minus the BASE_FEE), and start a
		# new one if 'size' is reached
		batch.append([aid, pay - XLM_Decimal(BASE_FEE / XLM_STROOP)])
		if len(batch) >= size:
			payouts.append(batch)  # All these payments will be a single transaction
			batch = []
	# The last batch may have less than 'size' payments
	payouts.append(batch)
	return payouts


def make_payment_op(account_id, amount):
	return Payment({
		'destination': account_id,
		'amount': str(amount),
		'asset': Asset('XLM')})


def main(inflation):
	# TODO: Let user select the connection type
	# The stellar/quickstart Docker image uses PostgreSQL
	#conn = sqlite3.connect(db_address)
	conn = psycopg2.connect(db_address)

	# Get the next sequence number for the transactions
	sequence = horizon.account(pool_address).get('sequence')
	inflation = XLM_Decimal(inflation)
	total_payments_cost = 0
	num_payments = 0
	total_fee_cost = 0

	# Create one transaction for each batch
	transactions = []
	for batch in accounts_payouts(conn, pool_address, inflation):
		op_count = 0
		ops = {'sequence': sequence, 'operations': []}
		for aid, amount in batch:
			# Check if the payment destination (aid) is valid (TOO SLOW!)
			#try:
			#	acc = horizon.account(aid)
			#except AccountNotExistError:
			#	continue
			#if not acc:
			#	continue
			# Include payment operation on ops{}
			ops['operations'].append(make_payment_op(aid, amount))
			op_count += 1

		# Build transaction
		tx = Transaction(
			source = pool_address,
			opts = ops
		)
		tx.memo = TextMemo("Thanks from lumenaut.net!");
		tx.fee = op_count * BASE_FEE;
		envelope = Te(tx=tx, opts={"network_id": network})
		# Append the transaction plain-text (JSON) on the list
		transactions.append(envelope.xdr().decode("utf-8"))

		# Calculate stats
		total_fee_cost += XLM_Decimal(tx.fee) / XLM_STROOP
		total_payments_cost += sum([
			XLM_Decimal(payment.amount) for payment in tx.operations])
		num_payments += len(tx.operations)

		# Prepare the next sequence number for the transactions
		sequence = int(sequence) + 1

	print((
		"## Stats ## \n"
		"Inflation received: %s\n"
		"A total of %s XLM paid over %s inflation payments "
		"using %s XLM in fees. \n"
		"Number of people that donated votes: %s\n") % (
			inflation,
			total_payments_cost,
			num_payments,
			total_fee_cost,
			len(donors),))

	with open("transactions.json", 'w') as outf:
		json.dump(transactions, outf)
	print("Done. Output to transactions.json")


TEST_AMT = 49855.2650163
if __name__ == '__main__':
	main(TEST_AMT)
