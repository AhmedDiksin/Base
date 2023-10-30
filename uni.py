import asyncio
import time
import random
from typing import Union, Type, Dict, Any

from hexbytes import HexBytes
from loguru import logger
from web3 import Web3
from eth_account import Account as EthereumAccount
from web3.contract import Contract
from web3.eth import AsyncEth
from web3.exceptions import TransactionNotFound

from config import RPC, ERC20_ABI, BASE_TOKENS, UNISWAP_CONTRACTS, UNISWAP_ROUTER_ABI, UNISWAP_FACTORY_ABI, UNISWAP_QUOTER_ABI

# Define GAS_MULTIPLIER here if it's not in config.py
GAS_MULTIPLIER = 1.2  # Example value, adjust as needed

# Placeholder for the sleep function from utils.sleeping
def sleep(min_time: float, max_time: float):
    time_to_sleep = random.uniform(min_time, max_time)
    time.sleep(time_to_sleep)


class Account:
    def __init__(self, account_id: int, private_key: str, chain: str) -> None:
        self.account_id = account_id
        self.private_key = private_key
        self.chain = chain
        self.explorer = RPC[chain]["explorer"]
        self.token = RPC[chain]["token"]

        self.w3 = Web3(
            Web3.HTTPProvider(random.choice(RPC[chain]["rpc"])),
            modules={"eth": (AsyncEth,)},
        )
        self.account = EthereumAccount.from_key(private_key)
        self.address = self.account.address

    def get_contract(self, contract_address: str, abi=None) -> Union[Type[Contract], Contract]:
        contract_address = Web3.to_checksum_address(contract_address)
        if abi is None:
            abi = ERC20_ABI
        contract = self.w3.eth.contract(address=contract_address, abi=abi)
        return contract
    async def get_balance(self, contract_address: str) -> Dict:
        contract_address = Web3.to_checksum_address(contract_address)
        contract = self.get_contract(contract_address)

        symbol = await contract.functions.symbol().call()
        decimal = await contract.functions.decimals().call()
        balance_wei = await contract.functions.balanceOf(self.address).call()

        balance = balance_wei / 10 ** decimal

        return {"balance_wei": balance_wei, "balance": balance, "symbol": symbol, "decimal": decimal}

    async def get_amount(self, from_token: str, min_amount: float, max_amount: float, decimal: int, all_amount: bool, min_percent: int, max_percent: int) -> [int, float, float]:
        random_amount = round(random.uniform(min_amount, max_amount), decimal)
        random_percent = random.randint(min_percent, max_percent)
        percent = 1 if random_percent == 100 else random_percent / 100

        if from_token == "ETH":
            balance = await self.w3.eth.get_balance(self.address)
            amount_wei = int(balance * percent) if all_amount else Web3.to_wei(random_amount, "ether")
            amount = Web3.from_wei(int(balance * percent), "ether") if all_amount else random_amount
        else:
            balance_info = await self.get_balance(BASE_TOKENS[from_token])
            amount_wei = int(balance_info["balance_wei"] * percent) if all_amount else int(random_amount * 10 ** balance_info["decimal"])
            amount = balance_info["balance"] * percent if all_amount else random_amount
            balance = balance_info["balance_wei"]

        return amount_wei, amount, balance

    async def check_allowance(self, token_address: str, contract_address: str) -> int:
        token_address = Web3.to_checksum_address(token_address)
        contract_address = Web3.to_checksum_address(contract_address)

        contract = self.w3.eth.contract(address=token_address, abi=ERC20_ABI)
        amount_approved = await contract.functions.allowance(self.address, contract_address).call()

        return amount_approved

    async def approve(self, amount: float, token_address: str, contract_address: str) -> None:
        token_address = Web3.to_checksum_address(token_address)
        contract_address = Web3.to_checksum_address(contract_address)

        contract = self.w3.eth.contract(address=token_address, abi=ERC20_ABI)

        allowance_amount = await self.check_allowance(token_address, contract_address)
        if amount > allowance_amount or amount == 0:
            approve_amount = 2 ** 128 if amount > allowance_amount else 0

            tx = {
                "chainId": await self.w3.eth.chain_id,
                "from": self.address,
                "nonce": await self.w3.eth.get_transaction_count(self.address)
            }

            transaction = await contract.functions.approve(contract_address, approve_amount).build_transaction(tx)
            signed_txn = await self.sign(transaction)

            txn_hash = await self.send_raw_transaction(signed_txn)

            await self.wait_until_tx_finished(txn_hash.hex())
            await sleep(5, 20)  # Random sleep between 5 to 20 seconds

    async def sign(self, transaction) -> Any:
        max_priority_fee_per_gas = int(await self.w3.eth.max_priority_fee * GAS_MULTIPLIER)
        max_fee_per_gas = int((await self.w3.eth.gas_price + max_priority_fee_per_gas) * GAS_MULTIPLIER)

        gas = await self.w3.eth.estimate_gas(transaction)
        gas = int(gas * GAS_MULTIPLIER)

        transaction.update({
            "maxPriorityFeePerGas": max_priority_fee_per_gas,
            "maxFeePerGas": max_fee_per_gas,
            "gas": gas
        })

        # Carefully handle private key: Ensure it's used only for signing and isn't printed or exposed elsewhere
        signed_txn = self.w3.eth.account.sign_transaction(transaction, self.private_key)

        return signed_txn

    async def send_raw_transaction(self, signed_txn) -> HexBytes:
        txn_hash = await self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        return txn_hash

    async def wait_until_tx_finished(self, hash: str, max_wait_time=180) -> None:
        start_time = time.time()
        while True:
            try:
                receipts = await self.w3.eth.get_transaction_receipt(hash)
                status = receipts.get("status")
                if status == 1:
                    return
                elif status is None:
                    await asyncio.sleep(0.3)
                else:
                    return
            except TransactionNotFound:
                if time.time() - start_time > max_wait_time:
                    return
                await asyncio.sleep(1)

class Uniswap(Account):
    def __init__(self, account_id: int, private_key: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="base")
        self.swap_contract = self.get_contract(UNISWAP_CONTRACTS["router"], UNISWAP_ROUTER_ABI)

    async def get_tx_data(self) -> Dict:
        tx = {
            "chainId": await self.w3.eth.chain_id,
            "from": self.address,
            "nonce": await self.w3.eth.get_transaction_count(self.address),
        }
        return tx

    async def get_pool(self, from_token: str, to_token: str):
        factory = self.get_contract(UNISWAP_CONTRACTS["factory"], UNISWAP_FACTORY_ABI)
        pool = await factory.functions.getPool(
            Web3.to_checksum_address(BASE_TOKENS[from_token]),
            Web3.to_checksum_address(BASE_TOKENS[to_token]),
            500
        ).call()
        return pool

    async def get_min_amount_out(self, from_token: str, to_token: str, amount: int, slippage: float):
        quoter = self.get_contract(UNISWAP_CONTRACTS["quoter"], UNISWAP_QUOTER_ABI)
        quoter_data = await quoter.functions.quoteExactInputSingle((
            Web3.to_checksum_address(BASE_TOKENS[from_token]),
            Web3.to_checksum_address(BASE_TOKENS[to_token]),
            amount,
            500,
            0
        )).call()
        return int(quoter_data[0] - (quoter_data[0] / 100 * slippage))

    async def swap_to_eth(self, from_token: str, to_token: str, amount: int, slippage: int):
        await self.approve(amount, BASE_TOKENS[from_token], UNISWAP_CONTRACTS["router"])
        tx_data = await self.get_tx_data()
        deadline = int(time.time()) + 1000000
        min_amount_out = await self.get_min_amount_out(from_token, to_token, amount, slippage)
        transaction_data = self.swap_contract.encodeABI(
            fn_name="exactInputSingle",
            args=[(
                Web3.to_checksum_address(BASE_TOKENS[from_token]),
                Web3.to_checksum_address(BASE_TOKENS[to_token]),
                500,
                self.address,
                amount,
                min_amount_out,
                0
            )]
        )
        contract_txn = await self.swap_contract.functions.multicall(
            deadline, [transaction_data]
        ).build_transaction(tx_data)
        return contract_txn

async def swap(self):
        amount_wei = Web3.to_wei(random.uniform(0.0001, 0.0002), "ether")
        contract_txn = await self.swap_to_eth("DAI", "ETH", amount_wei, 1)  # 1% slippage
        signed_txn = await self.sign(contract_txn)
        txn_hash = await self.send_raw_transaction(signed_txn)
        await self.wait_until_tx_finished(txn_hash.hex())

async def swap(
        self,
        from_token: str,
        to_token: str,
        min_amount: float,
        max_amount: float,
        decimal: int,
        slippage: int,
        all_amount: bool,
        min_percent: int,
        max_percent: int
):
    amount_wei, _, _ = await self.get_amount(
        from_token,
        min_amount,
        max_amount,
        decimal,
        all_amount,
        min_percent,
        max_percent
    )

    pool = await self.get_pool(from_token, to_token)

    if pool != ZERO_ADDRESS:
        if from_token == "ETH":
            contract_txn = await self.swap_to_token(from_token, to_token, amount_wei, slippage)
        else:
            contract_txn = await self.swap_to_eth(from_token, to_token, amount_wei, slippage)

        signed_txn = await self.sign(contract_txn)
        txn_hash = await self.send_raw_transaction(signed_txn)
        await self.wait_until_tx_finished(txn_hash.hex())
    else:
        logger.error(f"[{self.account_id}][{self.address}] Swap path {from_token} to {to_token} not found!")



async def main():
    # Define the parameters for the swap (Modify these as per your requirements)
    account_id = 1  # Just an example, use your own value
    private_key = "3a4c8274e4982ca4af0f7ca906f5bdc85e698ee3c104ed3ea8a0fde089a62fe6"  # WARNING: Never hard-code or expose your private key!
    if not private_key or private_key == "YOUR_PRIVATE_KEY_HERE":
        raise ValueError("Please replace the PRIVATE_KEY_PLACEHOLDER with your actual private key.")

    from_token = "DAI"
    to_token = "ETH"
    min_amount = 0.0001
    max_amount = 0.0002
    decimal = 18  # Assuming both tokens use 18 decimals
    slippage = 1  # 1% slippage, for example
    all_amount = False  # Whether to swap all available balance
    min_percent = 10  # Just an example
    max_percent = 90  # Just an example

    # Create an instance of the Uniswap class
    uni = Uniswap(account_id=account_id, private_key=private_key)

    # Execute the swap
    await uni.swap(
        from_token=from_token,
        to_token=to_token,
        min_amount=min_amount,
        max_amount=max_amount,
        decimal=decimal,
        slippage=slippage,
        all_amount=all_amount,
        min_percent=min_percent,
        max_percent=max_percent
    )

if __name__ == '__main__':
    asyncio.run(main())