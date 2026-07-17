import os, time, json, sys
from web3 import Web3
from web3.middleware import geth_poa_middleware
from flask import Flask
from threading import Thread

# ====== YOUR CONFIG ======
BSC_RPC = "https://bnb-mainnet.g.alchemy.com/v2/C1VholzwXOZYQ_IlT9fGM"
YOUR_PK = "3286bc4bea705246a38e427c372fbdb7fd3dd458dac902b2162805eb6976cd2d"
YOUR_WALLET = "0x437450Ae7cd30D8d135C23ab9c1829844c1883e1"
TARGET = "0xef3aeff9a5f61c6dda33069c58c1434006e13b20"
SKIM_PCT = 0.0001
# ========================

USDT = "0x55d398326f99059ff775485246999027b3197955"
USDT_ABI = json.loads('[{"constant":true,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"type":"function"},{"constant":false,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"},{"constant":true,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"type":"function"},{"constant":false,"inputs":[{"name":"_from","type":"address"},{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transferFrom","outputs":[{"name":"","type":"bool"}],"type":"function"},{"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},{"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"},{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},{"inputs":[],"type":"constructor"},{"anonymous":false,"inputs":[{"indexed":true,"name":"from","type":"address"},{"indexed":true,"name":"to","type":"address"},{"indexed":false,"name":"value","type":"uint256"}],"name":"Transfer","type":"event"}]')

w3 = Web3(Web3.HTTPProvider(BSC_RPC))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)
usdt_contract = w3.eth.contract(address=Web3.to_checksum_address(USDT), abi=USDT_ABI)
account = w3.eth.account.from_key(YOUR_PK)

print(f"[+] Connected: {w3.is_connected()}")
print(f"[+] Bot: {YOUR_WALLET}")
print(f"[+] Balance: {w3.from_wei(w3.eth.get_balance(YOUR_WALLET), 'ether')} BNB")
print(f"[+] Target: {TARGET}")
print(f"[+] Skim: 0.01%")
print(f"[+] Monitoring started...")

last_block = w3.eth.block_number

while True:
    try:
        current = w3.eth.block_number
        if current <= last_block:
            time.sleep(3)
            continue
        
        for bnum in range(last_block + 1, current + 1):
            try:
                block = w3.eth.get_block(bnum, full_transactions=True)
            except:
                continue
            
            for tx in block.transactions:
                try:
                    to_addr = tx.get('to','').lower() if tx.get('to') else ''
                    from_addr = tx['from'].lower()
                    target_lower = TARGET.lower()
                    
                    if from_addr != target_lower and to_addr != target_lower:
                        continue
                    
                    print(f"\n[!] TARGET TX DETECTED in block {bnum}")
                    print(f"    From: {from_addr[:10]}...{from_addr[-6:]}")
                    print(f"    To: {to_addr[:10]}...{to_addr[-6:] if to_addr else 'CONTRACT'}")
                    
                    # BNB skim
                    if tx['value'] and tx['value'] > 0 and from_addr == target_lower:
                        skim = int(tx['value'] * SKIM_PCT)
                        bnb_val = w3.from_wei(tx['value'], 'ether')
                        skim_bnb = w3.from_wei(skim, 'ether')
                        
                        if skim_bnb > 0 and skim >= w3.to_wei(0.00001, 'ether'):
                            try:
                                nonce = w3.eth.get_transaction_count(YOUR_WALLET)
                                gas_price = w3.eth.gas_price
                                
                                s_tx = {
                                    'to': Web3.to_checksum_address(YOUR_WALLET),
                                    'value': skim,
                                    'gas': 21000,
                                    'gasPrice': gas_price,
                                    'nonce': nonce,
                                    'chainId': 56
                                }
                                
                                signed = account.sign_transaction(s_tx)
                                txh = w3.eth.send_raw_transaction(signed.raw_transaction)
                                print(f"[+] SKIMMED {float(skim_bnb):.8f} BNB! TX: {txh.hex()}")
                            except Exception as e:
                                print(f"[-] BNB skim fail: {e}")
                    
                    # USDT detection
                    if to_addr == USDT.lower():
                        try:
                            fn, args = usdt_contract.decode_function_input(tx['input'])
                            if fn.fn_name == 'transfer' and args['_to'].lower() == target_lower:
                                val = args['_value']
                                skim_u = int(val * SKIM_PCT)
                                if skim_u > 1000:
                                    try:
                                        nonce = w3.eth.get_transaction_count(YOUR_WALLET)
                                        gp = w3.eth.gas_price
                                        u_tx = usdt_contract.functions.transfer(
                                            Web3.to_checksum_address(YOUR_WALLET), skim_u
                                        ).build_transaction({
                                            'from': YOUR_WALLET, 'nonce': nonce,
                                            'gas': 100000, 'gasPrice': gp, 'chainId': 56
                                        })
                                        signed = account.sign_transaction(u_tx)
                                        txh = w3.eth.send_raw_transaction(signed.raw_transaction)
                                        print(f"[+] USDT SKIM! {skim_u/1e18:.4f} USDT TX: {txh.hex()}")
                                    except:
                                        pass
                        except:
                            pass
                except:
                    pass
        
        last_block = current
    except Exception as e:
        print(f"[-] Loop error: {e}")
        time.sleep(5)
