import json
from stellar_base.builder import Builder

accounts = {}

with open("accounts.json") as data:
	accounts = json.load(data)

print("Building...")

builder = Builder(secret = input("Enter Secret Key: "))

for address, amount in accounts.items():
	builder.append_payment_op(address, amount, "XLM")

builder.add_text_memo("Inflation payment")

print("Signing...")

builder.sign()
xdr = builder.to_xdr()

with open("xdr.txt", 'w') as output:
	output.write(xdr)
	
print("Written to xdr.txt")