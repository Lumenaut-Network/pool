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

def XLM_Decimal(n):
	return Decimal(n).quantize(Decimal('.0000001'), rounding=ROUND_DOWN)

def add_donation(donation, payout):
	donation = base64.b64decode(donation).decode("utf-8")
	pct, address = Decimal(int(donation[:3]) / 100).quantize(Decimal('.01')), donation[3:]
	amt = XLM_Decimal(payout * pct)
	if address in donations.keys():
		donations[address] += amt
	else:
		donations[address] = amt
	return pct

def calculate_payout(cur, aid, bal, donation):
	bal /= 10000000 # amount in lumens
	payout = XLM_Decimal(bal * 0.01 / 52)

	donation_cut = 0
	if donation:
		donation_cut = add_donation(donation, payout)
	donation_cut = XLM_Decimal(payout * donation_cut)

	return payout - donation_cut

def accounts_payout(conn, pool_addr, size=100):
	cur = conn.cursor()
	cur.execute(select_account_op, (pool_addr, ))
	payouts = []
	while True:
		batch = cur.fetchmany(size)
		if not batch or batch == ():
			break
		payouts.append([(aid, calculate_payout(cur, aid, balance, donation)) for aid, balance, donation in batch])

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

def main():
	conn = sqlite3.connect(db_address)
	transactions = []

	sequence = horizon.account(pool_address).get('sequence')
	total_payments_cost = 0
	total_fee_cost = 0

	for batch in accounts_payout(conn, pool_address):
		tx = Transaction(
			source = pool_address,
			opts = {
				'sequence': sequence,
				'operations': [make_payment_op(aid, amount) for aid, amount in batch]
			}
		)
		tx.fee = len(tx.operations) * 100
		total_fee_cost += tx.fee
		total_payments_cost += sum([Decimal(payment.amount) for payment in tx.operations])
		envelope = Te(tx = tx, opts = {"network_id": network})
		transactions.append(envelope.xdr().decode("utf-8"))
		sequence = int(sequence) + 1

	with open("transactions.dat", 'w') as outf:
		json.dump(transactions, outf)
	print("Done. Output to transactions.dat")

if __name__ == '__main__': main()