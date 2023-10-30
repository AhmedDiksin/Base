import time
from typing import Dict
import asyncio

from loguru import logger
from web3 import Web3

from utils.gas_checker import check_gas
from utils.helpers import retry
from account import Account

from config import (
    UNISWAP_ROUTER_ABI,
    UNISWAP_CONTRACTS,
    UNISWAP_QUOTER_ABI,
    UNISWAP_FACTORY_ABI,
    BASE_TOKENS, ZERO_ADDRESS,
)


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

    async def swap_to_token(self, from_token: str, to_token: str, amount: int, slippage: int):
        tx_data = await self.get_tx_data()
        tx_data.update({"value": amount})

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

    async def swap_to_eth(self, from_token: str, to_token: str, amount: int, slippage: int):
        await self.approve(amount, BASE_TOKENS[from_token], UNISWAP_CONTRACTS["router"])

        tx_data = await self.get_tx_data()
        tx_data.update({"nonce": await self.w3.eth.get_transaction_count(self.address)})

        deadline = int(time.time()) + 1000000

        min_amount_out = await self.get_min_amount_out(from_token, to_token, amount, slippage)

        transaction_data = self.swap_contract.encodeABI(
            fn_name="exactInputSingle",
            args=[(
                Web3.to_checksum_address(BASE_TOKENS[from_token]),
                Web3.to_checksum_address(BASE_TOKENS[to_token]),
                500,
                "0x0000000000000000000000000000000000000002",
                amount,
                min_amount_out,
                0
            )]
        )

        unwrap_data = self.swap_contract.encodeABI(
            fn_name="unwrapWETH9",
            args=[
                min_amount_out,
                self.address
            ]

        )

        contract_txn = await self.swap_contract.functions.multicall(
            deadline,
            [transaction_data, unwrap_data]
        ).build_transaction(tx_data)

        return contract_txn

    @retry
    @check_gas
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
        amount_wei, amount, balance = await self.get_amount(
            from_token,
            min_amount,
            max_amount,
            decimal,
            all_amount,
            min_percent,
            max_percent
        )

        logger.info(
            f"[{self.account_id}][{self.address}] Swap on Uniswap – {from_token} -> {to_token} | {amount} {from_token}"
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

    from_token = "ETH"
    to_token = "DAI"
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