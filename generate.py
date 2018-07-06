import sqlite3, json, base64, sys

from decimal import Decimal, ROUND_DOWN, InvalidOperation

from stellar_base.asset import Asset
from stellar_base.operation import Payment
from stellar_base.transaction import Transaction
from stellar_base.transaction_envelope import TransactionEnvelope as Te
from stellar_base.horizon import horizon_testnet, horizon_livenet
from stellar_base.utils import AccountNotExistError

pool_address = "GCCD6AJOYZCUAQLX32ZJF2MKFFAUJ53PVCFQI3RHWKL3V47QYE2BNAUT"
db_address = "../core/stellar.db"

select_donations_op = """
	SELECT * FROM accountdata WHERE
	`dataname` LIKE 'Lumenaut.net donation%'"""

select_accounts_op = """
	SELECT `accounts`.`accountid`, `balance` FROM `accounts`
	WHERE `inflationdest`='%s'""" % pool_address

select_total_balance = "SELECT Sum(balance) FROM accounts WHERE `inflationdest`=?"
select_num_accounts = "SELECT Count(*) FROM accounts WHERE `inflationdest`=?"
select_sequence_num = "SELECT seqnum FROM accounts WHERE `accountid`=?"

network = "PUBLIC"
horizon = horizon_livenet()

BASE_FEE = 100
XLM_STROOP = 10000000
XLM_FEE = Decimal(BASE_FEE / XLM_STROOP)

donation_payouts = {}

def writeflushed(out):
	sys.stdout.write(out)
	sys.stdout.flush()


def XLM_Decimal(n):
	# 7 decimal places is the longest supported
	return Decimal(n).quantize(Decimal('.0000001'), rounding=ROUND_DOWN)


def query_one(cursor, query_str, args):
	cursor.execute(query_str, args)
	return cursor.fetchone()[0]

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


def accounts_payouts(cur, pool_addr, inflation, size=100):
	total_balance = XLM_Decimal(query_one(cur, select_total_balance, (pool_address, )))
	num_accounts = query_one(cur, select_num_accounts, (pool_address, ))

	cur.execute(select_donations_op)

	donations = {}
	for row in cur:
		donor = row[0]
		donation = parse_donation(row[2])
		
		if donation != None:
			donation_address, percentage = donation

			if donor not in donations:
				donations[donor] = {}
			donations[donor][donation_address] = percentage

	payouts = []
	batch = []

	cur.execute(select_accounts_op)

	i = 1.0

	for row in cur:
		writeflushed("\rCalculating donation amounts: %d%%" % ((i / num_accounts) * 100))
		i += 1

		accountid = row[0]
		account_balance = XLM_Decimal(row[1])
		account_inflation = (account_balance / total_balance) * inflation

		if accountid in donations:
			inflation_sub = 0

			for address in donations[accountid]:
				pct = donations[accountid][address]
				donation_amt = account_inflation * pct
				donation_payouts[address] = XLM_Decimal(donation_payouts.get(address, 0) + donation_amt)
				inflation_sub += donation_amt + XLM_FEE # take the transaction fee from donations (even though they will be bundled)

			account_inflation -= inflation_sub

		batch.append((accountid, XLM_Decimal(account_inflation - XLM_FEE)))

		if len(batch) >= 100:
			payouts.append(batch)
			batch = []

	writeflushed("\rCalculated donation amounts successfully.\n")

	for address in donation_payouts:
		batch.append((address, donation_payouts[address]))

		if len(batch) >= 100:
			payouts.append(batch)
			batch = []

	if len(batch) > 0:
		payouts.append(batch)
		batch = []

	return payouts, total_balance, num_accounts


def make_payment_op(account_id, amount):
	return Payment({
		'destination': account_id,
		'source': pool_address,
		'amount': str(amount),
		'asset': Asset('XLM')
	})


def main(inflation):
	# TODO: Let user select the connection type
	# The stellar/quickstart Docker image uses PostgreSQL
	conn = sqlite3.connect(db_address)
	cur = conn.cursor()

	# Get the next sequence number for the transactions
	sequence = query_one(cur, select_sequence_num, (pool_address, ))

	inflation = XLM_Decimal(inflation)
	transactions = []

	num_payments = 0
	total_payments_cost = XLM_Decimal(0)
	total_fee_cost = XLM_Decimal(0)

	batches, total_balance, num_accounts = accounts_payouts(cur, pool_address, inflation)
	
	num_batches = len(batches)
	dest_sequence = sequence + num_batches
	i = 1.0

	# Create one transaction for each batch
	for batch in batches:
		writeflushed("\rCreating and encoding transactions: %d%%" % (i / num_batches * 100))
		i += 1

		operations = []
		for aid, amount in batch:
			# Include payment operation on ops{}
			payment_op = make_payment_op(aid, amount)
			operations.append(payment_op)

			total_payments_cost += amount

		# Build transaction
		tx = Transaction(
			source=pool_address,
			opts={"sequence": sequence, "operations": operations, "fee": len(batch) * BASE_FEE}
		)

		# Bundle transaction into an envelope to be encoded to xdr
		envelope = Te(tx=tx, opts={"network_id": network})

		# Append the transaction plain-text (JSON) on the list
		transactions.append(envelope.xdr().decode("utf-8"))

		# Calculate stats
		total_fee_cost += tx.fee
		num_payments += len(operations)

		# Prepare the next sequence number for the transactions
		sequence += 1

	with open("transactions.json", 'w') as outf:
		json.dump(transactions, outf)

	writeflushed("\rSuccessfully built transaction file: written to transactions.json.\n\n")

	print((
		"Stats: \n"
		"\tInflation received: %s\n"
		"\tNumber of accounts voting for Lumenaut: %d (%s XLM)\n"
		"\tA total of %s XLM paid over %s inflation payments using %s XLM in fees.\n"
		"\tNumber of transactions needed: %s\n"
		"\tNumber of unique donation addresses: %s\n") % (
			inflation,
			num_accounts,
			(total_balance / XLM_STROOP),
			total_payments_cost,
			num_payments,
			(total_fee_cost / XLM_STROOP),
			len(transactions),
			len(donation_payouts)
		)
	)


if __name__ == '__main__':
	main(49855.2650163) # test amount