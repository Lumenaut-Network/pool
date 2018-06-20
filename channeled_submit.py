import threading, json, sys, requests

from stellar_base.keypair import Keypair
from stellar_base.transaction_envelope import TransactionEnvelope
from stellar_base.horizon import horizon_testnet, horizon_livenet
from stellar_base.stellarxdr import Xdr

horizon_instance = horizon_testnet
horizon = horizon_instance()

channel_keypairs = []
with open("channel_keypairs") as f:
	for line in f.readlines():
		channel_keypairs.append(Keypair.from_seed(line.strip()))

num_channels 		= len(channel_keypairs)
channel_accounts 	= [None] * num_channels
channels_loaded 	= False

def get_account(address, index):
	account = horizon.account(address)
	channel_accounts[index] = account


def load_channels():
	threads = []
	for i in range(num_channels):
		t = threading.Thread(target=get_account, args=(channel_keypairs[i].address().decode(),i))
		threads.append(t)
		t.start()

	for i in range(num_channels): threads[i].join()
	channels_loaded = True

	# TODO: assert channels exist?

	return all(channel_accounts)


def split_transactions(transaction_file):
	with open(transaction_file) as f:
		transactions = json.loads(f.read())

	(fair_trans, extra) = divmod(len(transactions), num_channels)
	per_channel = [fair_trans] * num_channels
	i = 0
	while extra > 0:
		per_channel[i] += 1
		extra -= 1
		i += 1

	channel_transactions = [None] * num_channels
	offset = 0
	for i in range(num_channels):
		num_trans = per_channel[i]
		for_channel = transactions[offset : offset + num_trans]
		channel_transactions[i] = for_channel
		offset += num_trans

	# check transactions have been split fairly
	print("Divided transactions, split: %s" % str(per_channel))

	return channel_transactions
	

def channel_worker(channel_index, transactions):
	thread_horizon 		= horizon_instance()
	channel_keypair 	= channel_keypairs[channel_index]
	channel_address 	= channel_keypair.address().decode()
	channel_sequence 	= int(channel_accounts[channel_index].get("sequence")) + 1

	failed = []
	for i in range(len(transactions)):
		env = TransactionEnvelope.from_xdr(transactions[i])

		env.tx.source 	= channel_address
		env.tx.sequence = channel_sequence

		env.sign(channel_keypair)

		res = requests.post("https://horizon-testnet.stellar.org/transactions", data={"tx": env.xdr()}, )
		res = res.json()

		if res["status"] < 400:
			channel_sequence += 1
		else:
			#print(res)
			failed.append((i, res))

	print("Channel #%d thread finished, %d transaction(s) failed" % (channel_index + 1, len(failed)))


def main(transaction_file):
	load_channels()
	transactions = split_transactions(transaction_file)

	print("Starting submission")
	threads = []
	for i in range(num_channels):
		t = threading.Thread(target=channel_worker, args=(i, transactions[i]))
		threads.append(t)
		t.start()

	for i in range(num_channels): 
		threads[i].join()

	print("Finished")


if __name__ == "__main__":
	main(sys.argv[1]) # file containing SIGNED transactions