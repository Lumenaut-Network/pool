import logging

import click

from stellar_base.keypair import Keypair
from stellar_base.utils import DecodeError
from stellar_base.transaction import Transaction
from stellar_base.transaction_envelope import TransactionEnvelope as Te
from stellar_base.operation import SetOptions
from stellar_base.operation import CreateAccount
from stellar_base.horizon import horizon_livenet, horizon_testnet

logger = logging.getLogger(__name__)


SIGNING_THRESHOLD = {
	"low": 3,
	"medium": 3,
	"high": 4
}
STARTING_BALANCE = "5"

network = "PUBLIC"
horizon = horizon_livenet()


def generate_pool_keypair(desired_tail=None):
	kp = None

	if desired_tail:

		logger.debug("Looking for address ending in '%s'..." % (desired_tail,))
		while True:
			kp = Keypair.random()
			if kp.address().decode()[-len(desired_tail):] == desired_tail:
				break
	else:
		kp = Keypair.random()

	return kp


def create_pool_account(horizon, network_id, account_secret_key, pool_keypair):
	funding_account_kp = None
	try:
		funding_account_kp = Keypair.from_seed(account_secret_key)
	except DecodeError:
		logger.error("Invalid secret key, aborting")
		return False

	creation_operation = CreateAccount({
		"destination": pool_keypair.address().decode(),
		"starting_balance": STARTING_BALANCE
	})

	sequence = horizon.account(
		funding_account_kp.address().decode()).get('sequence')

	tx = Transaction(
		source=funding_account_kp.address().decode(),
		opts={
			'sequence': sequence,
			'operations': [creation_operation],
		},
	)

	envelope = Te(tx=tx, opts={"network_id": network_id})
	envelope.sign(funding_account_kp)

	xdr = envelope.xdr()
	response = horizon.submit(xdr)
	if "_links" in response:
		logger.debug("Creation of account transaction link: %s" % (
			response["_links"]["transaction"]["href"],))
		return True
	else:
		logger.error("Failed to create account. Dumping response:")
		logger.error(response)
		return False


def get_signers():
	signers = []
	with open('signers.txt') as f:
		signers = f.read().splitlines()
	return signers


def set_account_signers(pool_keypair, threshold):
	pool_address = pool_keypair.address().decode()

	operations = [
		SetOptions({
			"signer_address": signer_address,
			"signer_weight": 1,
			"signer_type": "ed25519PublicKey",
			"source_account": pool_address
		})
		for signer_address in get_signers()
	]

	operations.append(
		SetOptions({
			"source_account": pool_address,
			"home_domain": bytes("lumenaut.net", "utf-8"),
			"master_weight": 0,
			"low_threshold": threshold["low"],
			"med_threshold": threshold["medium"],
			"high_threshold": threshold["high"],
			"inflation_dest": pool_address
		})
	)

	sequence = horizon.account(pool_address).get('sequence')
	tx = Transaction(
		source=pool_address,
		opts={
			'sequence': sequence,
			'fee': 100 * len(operations),
			'operations': operations,
		},
	)

	envelope = Te(tx=tx, opts={"network_id": network})
	envelope.sign(pool_keypair)

	xdr = envelope.xdr()
	response = horizon.submit(xdr)

	if "_links" in response:
		print(
			"Set options transaction href: ",
			response["_links"]["transaction"]["href"])
		print("Created successfully!")
	else:
		print("Failed to set account signers, dumping response:")
		print(response)


@click.command()
@click.option('--desired-tail', type=str, default=None)
@click.option('--funding-account-secret-key', type=str, prompt=True)
@click.option('--network-id', type=click.Choice(['TESTNET', 'PUBLIC']))
def main(desired_tail, funding_account_secret_key, network_id):
	horizon = (horizon_livenet() if network == 'PUBLIC' else horizon_testnet())
	pool_kp = generate_pool_keypair(desired_tail)
	print("Pool keypair: %s | %s" % (
		pool_kp.address().decode(), pool_kp.seed().decode()))

	if create_pool_account(
		horizon, network_id, funding_account_secret_key, pool_kp):
			set_account_signers(pool_kp, SIGNING_THRESHOLD)


if __name__ == "__main__":
	main()
