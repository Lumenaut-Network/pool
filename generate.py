import sqlite3, json, base64
from stellar_base.asset import Asset
from stellar_base.keypair import Keypair
from stellar_base.operation import Payment
from stellar_base.transaction import Transaction
from stellar_base.transaction_envelope import TransactionEnvelope as Te
from stellar_base.memo import TextMemo
from stellar_base.horizon import horizon_testnet, horizon_livenet

pool = Keypair.from_seed("SCIUAHZIIJKYP3L3WEQMZM6NUBMYUXFHUIKR2PDWYO43AQV6SHV35N6F")
network = "TESTNET"
db_address = "../stellar-core/stellar.db"

# credit to francesco for this

def total_accounts_balance(conn, pool_addr):
	cur = conn.cursor()
	cur.execute("SELECT sum(balance) FROM accounts WHERE inflationdest=?", (pool_addr, ))
	total_balance, = cur.fetchone()
	return total_balance


def pool_balance(conn, pool_addr):
	cur = conn.cursor()
	cur.execute("SELECT balance FROM accounts WHERE accountid=?", (pool_addr, ))
	balance, = cur.fetchone()
	return balance


def pool_share_payout(balance, accounts_balance, pool_balance):
	share = (balance / accounts_balance) * pool_balance
	return share / 10000000


def fetch_batch(cur, size):
	while True:
		batch = cur.fetchmany(size)
		if batch == [] or batch is None:
			break
		yield batch


def accounts_payout(conn, pool_addr, size=100):
	accounts_balance = total_accounts_balance(conn, pool_addr)
	balance = pool_balance(conn, pool_addr)
	cur = conn.cursor()
	cur.execute("SELECT accountid, balance FROM accounts WHERE inflationdest=?", (pool_addr, ))
	for batch in fetch_batch(cur, size):
		if not batch:
			break
		yield [(aid, pool_share_payout(balance, accounts_balance, balance)) for aid, balance in batch]


def make_payment_op(account_id, amount):
	return Payment({'destination': account_id, 'amount': str(amount), 'asset': Asset('XLM')})

def main():
	conn = sqlite3.connect(db_address)
	transactions = []

	horizon = horizon_testnet()
	sequence = horizon.account(pool.address().decode()).get('sequence')

	for batch in accounts_payout(conn, pool_address):
		tx = Transaction(
			source = pool.address().decode(),
			opts = {
				'sequence': sequence,
				'operations': [make_payment_op(aid, amount) for aid, amount in batch]
			}
		)
		envelope = Te(tx = tx, opts = {"network_id": network})
		envelope.sign(pool)
		transactions.append(envelope.xdr().decode("utf-8"))
		sequence = int(sequence) + 1

	with open("transactions.dat", 'w') as outf:
		json.dump(transactions, outf)
	print("Done. Output to transactions.dat")

if __name__ == '__main__': main()