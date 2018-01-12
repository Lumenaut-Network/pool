from stellar_base.keypair import Keypair
from stellar_base.transaction import Transaction
from stellar_base.transaction_envelope import TransactionEnvelope as Te
from stellar_base.operation import SetOptions
from stellar_base.horizon import horizon_testnet, horizon_livenet
import requests, sys

signers = []
with open('signers.txt') as f:
	signers = f.read().splitlines()

kp = None
if len(sys.argv > 1):
	desired_tail = sys.argv[1]

	print("looking for address ending in '" + desired_tail + "'...")
	while True:
		kp = Keypair.random()
		if kp.address().decode()[-len(desired_tail):] == desired_tail:
			break
else:
	kp = Keypair.random()

pool_address = kp.address().decode()

r = requests.get('https://horizon-testnet.stellar.org/friendbot?addr=' + pool_address)
print("Requesting initial funding...")

threshold = 3
operations = [
	SetOptions({
		"signer_address": address,
		"signer_weight": 1,
		"signer_type": "ed25519PublicKey",
		"source_account": kp.address().decode()
		}) 
	for address in signers
]

operations.append(
	SetOptions({
		"source_account": kp.address().decode(),
		"home_domain": bytes("lumenaut.net", "utf-8"),
		"master_weight": 1, 
		"low_threshold": threshold, 
		"med_threshold": threshold, 
		"high_threshold": threshold,
		"inflation_dest": kp.address().decode()
	})
)

horizon = horizon_testnet()
sequence = horizon.account(pool_address).get('sequence')
tx = Transaction(
	source = pool_address,
	opts = {
		'sequence': sequence,
		'fee': 100 * len(operations),
		'operations': operations,
	},
)
envelope = Te(tx = tx, opts = {"network_id": "TESTNET"})
envelope.sign(kp)
xdr = envelope.xdr()

print("Submitting xdr:")
print(xdr.decode("utf-8"))

response = horizon.submit(xdr)
print("Transaction href: ", response["_links"]["transaction"]["href"])