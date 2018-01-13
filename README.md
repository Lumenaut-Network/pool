# COMMUNITY INFLATION POOL
Requires the stellar-base package
	`pip3 install stellar-base`

## 1
`createpool.py` will generate an address (with a given vanity suffix if required) and add each address in `signers.txt` as signers to the account & set the threshold for any transaction to at least 3 signatures. (this will need to be changed for LIVENET)

## 2
`watch.py` will monitor operations on the stellar network, looking for INFLATION. Once seen, it triggers the payout calculations to begin

## 3
`generate.py` will scrape the stellar.db file used by stellar-core & create the payment transactions for that inflation period. These are json-encoded and saved into `transactions.dat`

## 4
`sign.py` or `sign.html` can be used to sign the `transactions.dat` file in bulk, making it easy for the signatories to sign off on that weeks payout. After signing, the updated `transactions.dat` file will need to be shared with the next signer (TODO: make a web app for this / client downloads transaction.dat, signs, uploads updated back to server for next signer)

## 5 
Everyone gets free money every week!