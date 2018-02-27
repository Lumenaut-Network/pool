# COMMUNITY INFLATION POOL
Requires the stellar-base package
	`pip3 install stellar-base`

## 1
`createpool.py` will generate an address (with a given vanity suffix if required) and add each address in `signers.txt` as signers to the account & set the threshold for any transaction to at least 3 signatures. (this will need to be changed for LIVENET)

## 2
`watch.py` will monitor operations on the stellar network, looking for INFLATION. Once seen, it triggers the payout calculations to begin

## 3
`generate.py` will scrape the stellar.db file created by stellar-core & create the payment transactions for that inflation period. These are json-encoded and saved into `transactions.dat`

## 4
`sign.py` or `sign.html` can be used to sign the `transactions.dat` file in bulk, making it easy for the signatories to sign off on that weeks payout. Alternatively, the multisig-coordinator can be used to streamline the process. See the repository [here](https://github.com/Lumenaut-Network/multisig-coordinator)

TODO:
- Experiment with submitting transactions via account channels
- More logging in case of failure