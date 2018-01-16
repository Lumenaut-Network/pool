import json
from stellar_base.builder import Builder
from stellar_base.horizon import horizon_testnet

network = "TESTNET"
horizon = horizon_testnet()

transactions_unsigned = []
with open("transactions.json", 'r') as tfile:
	transactions_unsigned = json.load(tfile)

key = input("Signing Key: ")
builder = Builder(secret=key, network=network)
amt_signed = 0
needed = 3
transactions = []
for xdr in transactions_unsigned:
	builder.import_from_xdr(xdr)
	amt_signed = len(builder.te.signatures) + 1
	builder.sign()
	transactions.append(builder.gen_xdr().decode("utf-8"))

print("Added signature. Transactions now signed by %s/%s parties." % (
	str(amt_signed), str(needed)))


if amt_signed >= needed:
	print("Submitting " + str(len(transactions)) + "transactions")
	i = 1
	for xdr in transactions:
		try:
			response = horizon.submit(builder.gen_xdr())
			print("Transaction %s link: %s" % (
				str(i), response["_links"]["transaction"]["href"]))
			i += 1
		except Exception as e:
			raise e
else:
	print("Updating transactions.json")
	with open("transactions.json", 'w') as outf:
		json.dump(transactions, outf)
