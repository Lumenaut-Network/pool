import sqlite3, json, base64
from decimal import *

from stellar_base.asset import Asset
from stellar_base.keypair import Keypair
from stellar_base.operation import Payment
from stellar_base.transaction import Transaction
from stellar_base.transaction_envelope import TransactionEnvelope as Te
from stellar_base.memo import TextMemo
from stellar_base.horizon import horizon_testnet, horizon_livenet

pool_address = "GCFXD4OBX4TZ5GGBWIXLIJHTU2Z6OWVPYYU44QSKCCU7P2RGFOOHTEST"
network = "TESTNET"
db_address = "../core/stellar.db"
select_account_op = "SELECT `accounts`.`accountid`, `balance`, `datavalue` FROM `accounts` \
					 LEFT JOIN `accountdata` ON `accountdata`.`accountid` = `accounts`.`accountid` AND `dataname`='lumenaut.net donation' \
					 WHERE `inflationdest`=?"
horizon = horizon_testnet()
donations = {}

BASE_FEE = 100
XLM_STROOP = 10000000

def XLM_Decimal(n):
	return Decimal(n).quantize(Decimal('.0000001'), rounding=ROUND_DOWN) # 7 decimal places is the longest supported

def add_donation(donation, payout):
	donation = base64.b64decode(donation).decode("utf-8")
	pct, address = Decimal(min(int(donation[:3]), 100) / 100).quantize(Decimal('.01')), donation[3:]
	amt = XLM_Decimal(payout * pct)

	if address in donations.keys():
		donations[address] += amt
	else:
		donations[address] = amt

	return pct

def calculate_payout(cur, inflation, total_balance, aid, bal, donation):
	bal = Decimal(bal - BASE_FEE * 2) / XLM_STROOP # amount in lumens (take 200 stroops each to cover transaction fees)
	bal_pct = bal / total_balance # higher precision
	payout = XLM_Decimal(inflation * bal_pct)

	donation_cut = 0
	if donation:
		donation_cut = add_donation(donation, payout)

	donation_cut = XLM_Decimal(payout * donation_cut)

	return payout - donation_cut

def accounts_payout(conn, pool_addr, inflation, size=100):
	cur = conn.cursor()
	cur.execute("SELECT Sum(balance) FROM accounts WHERE `inflationdest`=?", (pool_address, ))
	total_balance = Decimal(cur.fetchone()[0]) / XLM_STROOP

	cur.execute(select_account_op, (pool_addr, ))
	payouts = []
	while True:
		batch = cur.fetchmany(size)
		if not batch or batch == ():
			break
		payouts.append([(aid, calculate_payout(cur, inflation, total_balance, aid, balance, donation)) for aid, balance, donation in batch])

	donation_payouts = []
	batch = []
	for address, amount in donations.items():
		batch.append((address, amount))
		if len(batch) >= size:
			donation_payouts.append(batch)
			batch = []
	donation_payouts.append(batch)

	payouts.extend(donation_payouts)
	return payouts


def make_payment_op(account_id, amount):
	return Payment({'destination': account_id, 'amount': str(amount), 'asset': Asset('XLM')})

def main(inflation):
	inflation = XLM_Decimal(inflation)

	conn = sqlite3.connect(db_address)
	transactions = []

	sequence = horizon.account(pool_address).get('sequence')
	total_payments_cost = 0
	num_payments = 0
	total_fee_cost = 0

	for batch in accounts_payout(conn, pool_address, inflation):
		tx = Transaction(
			source = pool_address,
			opts = {
				'sequence': sequence,
				'operations': [make_payment_op(aid, amount) for aid, amount in batch]
			}
		)
		tx.fee = len(tx.operations) * 100
		envelope = Te(tx = tx, opts = {"network_id": network})
		transactions.append(envelope.xdr().decode("utf-8"))

		total_fee_cost += tx.fee / XLM_STROOP
		total_payments_cost += sum([Decimal(payment.amount) for payment in tx.operations])
		num_payments += len(tx.operations)

		sequence = int(sequence) + 1

	print(
		"Stats: \n\
		Inflation received: " + str(inflation) + "\n\
		A total of " + str(total_payments_cost) +\
		" XLM paid over " + str(num_payments) +\
		" inflation payments using " + str(total_fee_cost) + " XLM in fees. \n\
		People donated " + str(sum([n for n in donations.values()])) +\
		" XLM to " + str(len(donations.keys())) +\
		" different addresses.\n"
	)

	with open("transactions.dat", 'w') as outf:
		json.dump(transactions, outf)
	print("Done. Output to transactions.dat")

TEST_AMT = 49855.2650163
if __name__ == '__main__': main(TEST_AMT)