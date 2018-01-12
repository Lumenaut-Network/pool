import json, base64
from stellar_base.builder import Builder
from stellar_base.keypair import Keypair

network = "TESTNET"

transactions_unsigned = []
with open("transactions.dat", 'r') as tfile:
	transactions_unsigned = json.load(tfile)

key = input("Signing Key: ")
amt_signed = 0
needed = 3
transactions = []
for xdr in transactions_unsigned:
	builder = Builder(secret = key, network=network)
	builder.import_from_xdr(xdr)
	amt_signed = len(builder.te.signatures) + 1
	builder.sign()
	transactions.append(builder.gen_xdr().decode("utf-8"))

print("Added signature. Transactions now signed by %s/%s parties." % (str(amt_signed), str(needed)))

if amt_signed >= needed:
	#print("Submitting...")
	#for xdr in transactions:
		#builder = Builder(secret = key)
		#builder.import_from_xdr(xdr)
		#builder.submit()
#else:
	print("Updating transactions.dat")
	with open("transactions.dat", 'w') as outf:
		json.dump(transactions, outf)