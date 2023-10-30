import json

with open('data/rpc.json') as file:
    RPC = json.load(file)

with open('data/abi/erc20_abi.json') as file:
    ERC20_ABI = json.load(file)

with open("accounts.txt", "r") as file:
    ACCOUNTS = [row.strip() for row in file]

with open('data/abi/base/bridge.json') as file:
    BASE_BRIDGE_ABI = json.load(file)

with open('data/abi/base/weth.json') as file:
    WETH_ABI = json.load(file)

with open("data/abi/uniswap/router.json", "r") as file:
    UNISWAP_ROUTER_ABI = json.load(file)

with open("data/abi/pancake/factory.json", "r") as file:
    UNISWAP_FACTORY_ABI = json.load(file)

with open("data/abi/uniswap/quoter.json", "r") as file:
    UNISWAP_QUOTER_ABI = json.load(file)


ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

BASE_BRIDGE_CONTRACT = "0x49048044D57e1C92A77f79988d21Fa8fAF74E97e"

ORBITER_CONTRACT = ""

BASE_TOKENS = {
    "ETH": "0x4200000000000000000000000000000000000006",
    "WETH": "0x4200000000000000000000000000000000000006",
    "USDBC": "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA",
    "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "DAI": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
}

UNISWAP_CONTRACTS = {
    "router": "0x2626664c2603336E57B271c5C0b26F421741e481",
    "factory": "0x33128a8fC17869897dcE68Ed026d694621f6FDfD",
    "quoter": "0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a",
}


