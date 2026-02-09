# 部署

好的，我们的池合约已经完成了。现在，让我们看看如何将它部署到本地 Ethereum 网络，以便稍后可以从前端应用程序中使用它。

## 选择本地区块链网络

智能合约开发需要运行一个本地网络，你可以在开发和测试期间将合约部署到该网络。这就是我们对此类网络的需求：
1. 真实的区块链。它必须是一个真实的 Ethereum 网络，而不是模拟。我们希望确保我们的合约在本地网络中的工作方式与在主网中完全相同。
1. 速度。我们希望我们的交易能够立即被挖出，以便我们可以快速迭代。
1. 以太币。为了支付交易费用，我们需要一些以太币，并且我们希望本地网络允许我们生成任意数量的以太币。
1. 作弊码。除了提供标准的 API 之外，我们还希望本地网络允许我们做更多的事情。例如，我们希望能够将合约部署到任何地址，从任何地址执行交易（伪装成其他地址），直接更改合约状态等。

截至今天，有多种解决方案：
1. Truffle Suite 的 [Ganache](https://trufflesuite.com/ganache/)。
1. [Hardhat](https://hardhat.org/)，它是一个开发环境，除了其他有用的东西之外，还包括一个本地节点。
1. Foundry 的 [Anvil](https://github.com/foundry-rs/foundry/tree/master/anvil)。

所有这些都是可行的解决方案，它们都可以满足我们的需求。话虽如此，项目一直在缓慢地从 Ganache（它是最古老的解决方案）迁移到 Hardhat（这似乎是目前最广泛使用的），现在又出现了新的解决方案：Foundry。Foundry 也是这些解决方案中唯一一个使用 Solidity 编写测试的（其他的使用 JavaScript）。此外，Foundry 还允许用 Solidity 编写部署脚本。因此，由于我们决定在所有地方使用 Solidity，我们将使用 Anvil 来运行本地开发区块链，并且我们将用 Solidity 编写部署脚本。

## 运行本地区块链

Anvil 不需要配置，我们可以使用一个命令来运行它，它会执行以下操作：

```shell
$ anvil --code-size-limit 50000
                             _   _
                            (_) | |
      __ _   _ __   __   __  _  | |
     / _` | | '_ \  \ \ / / | | | |
    | (_| | | | | |  \ V /  | | | |
     \__,_| |_| |_|   \_/   |_| |_|

    0.1.0 (d89f6af 2022-06-24T00:15:17.897682Z)
    https://github.com/foundry-rs/foundry
...
Listening on 127.0.0.1:8545
```

> 我们将编写不符合 Ethereum 合约大小限制（即 `24576` 字节）的大型合约，因此我们需要告诉 Anvil 允许更大的智能合约。

Anvil 运行一个 Ethereum 节点，所以这不是一个网络，但这没关系。默认情况下，它会创建 10 个账户，每个账户有 10,000 ETH。它会在启动时打印地址和相关的私钥——我们将在从 UI 部署和与合约交互时使用其中一个地址。

Anvil 在 `127.0.0.1:8545` 上公开了 JSON-RPC API 接口——这个接口是与 Ethereum 节点交互的主要方式。你可以在[这里](https://ethereum.org/en/developers/docs/apis/json-rpc/)找到完整的 API 参考。这是你可以通过 `curl` 调用它的方式：
```shell
$ curl -X POST -H 'Content-Type: application/json' \
  --data '{"id":1,"jsonrpc":"2.0","method":"eth_chainId"}' \
  http://127.0.0.1:8545
{"jsonrpc":"2.0","id":1,"result":"0x7a69"}
$ curl -X POST -H 'Content-Type: application/json' \
  --data '{"id":1,"jsonrpc":"2.0","method":"eth_getBalance","params":["0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266","latest"]}' \
  http://127.0.0.1:8545
{"jsonrpc":"2.0","id":1,"result":"0x21e19e0c9bab2400000"}
```

你也可以使用 `cast`（Foundry 的一部分）来做到这一点：
```shell
$ cast chain-id
31337
$ cast balance 0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266
10000000000000000000000
```

现在，让我们将池和管理器合约部署到本地网络。

## 首次部署

从本质上讲，部署合约意味着：
1. 将源代码编译成 EVM 字节码。
1. 发送包含字节码的交易。
1. 创建一个新地址，执行字节码的构造器部分，并将部署的字节码存储在该地址上。此步骤由 Ethereum 节点在你的合约创建交易被挖出时自动完成。

部署通常包括多个步骤：准备参数、部署辅助合约、部署主要合约、初始化合约等。脚本编写有助于自动化这些步骤，我们将用 Solidity 编写脚本！

创建 `scripts/DeployDevelopment.sol` 合约，内容如下：
```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.14;

import "forge-std/Script.sol";

contract DeployDevelopment is Script {
    function run() public {
      ...
    }
}
```

它看起来与测试合约非常相似，唯一的区别是它继承自 `Script` 合约，而不是 `Test`。并且，按照约定，我们需要定义 `run` 函数，该函数将成为我们部署脚本的主体。在 `run` 函数中，我们首先定义部署的参数：
```solidity
uint256 wethBalance = 1 ether;
uint256 usdcBalance = 5042 ether;
int24 currentTick = 85176;
uint160 currentSqrtP = 5602277097478614198912276234240;
```
这些是我们之前使用过的相同值。请注意，我们将要铸造 5042 USDC——这是我们将作为流动性提供给池的 5000 USDC，以及我们将在交换中出售的 42 USDC。

接下来，我们定义将作为部署交易执行的一组步骤（嗯，每个步骤将是一个单独的交易）。为此，我们使用 `startBroadcast/endBroadcast` 作弊码：
```solidity
vm.startBroadcast();
...
vm.stopBroadcast();
```

> 这些作弊码由 [Foundry 提供](https://github.com/foundry-rs/foundry/tree/master/forge#cheat-codes)。我们通过继承 `forge-std/Script.sol` 在脚本合约中获得了它们。

`broadcast()` 作弊码之后或 `startBroadcast()/stopBroadcast()` 之间的所有内容都会转换为交易，并且这些交易会发送到执行脚本的节点。

在广播作弊码之间，我们将放入实际的部署步骤。首先，我们需要部署代币：
```solidity
ERC20Mintable token0 = new ERC20Mintable("Wrapped Ether", "WETH", 18);
ERC20Mintable token1 = new ERC20Mintable("USD Coin", "USDC", 18);
```
没有代币我们就不能部署池，所以我们需要先部署它们。

> 由于我们正在部署到本地开发网络，我们需要自己部署代币。在主网和公共测试网络（Ropsten、Goerli、Sepolia）中，代币已经创建。因此，要部署到这些网络，我们需要编写特定于网络的部署脚本。

下一步是部署池合约：
```solidity
UniswapV3Pool pool = new UniswapV3Pool(
    address(token0),
    address(token1),
    currentSqrtP,
    currentTick
);
```

接下来是 Manager 合约部署：
```solidity
UniswapV3Manager manager = new UniswapV3Manager();
```

最后，我们可以将一些 ETH 和 USDC 铸造到我们的地址：
```solidity
token0.mint(msg.sender, wethBalance);
token1.mint(msg.sender, usdcBalance);
```

> Foundry 脚本中的 `msg.sender` 是在 `broadcast` 块中发送交易的地址。我们可以在运行脚本时设置它。

最后，在脚本末尾，添加一些 `console.log` 调用以打印已部署合约的地址：
```solidity
console.log("WETH address", address(token0));
console.log("USDC address", address(token1));
console.log("Pool address", address(pool));
console.log("Manager address", address(manager));
```

好的，让我们运行脚本（确保 Anvil 在另一个终端窗口中运行）：
```shell
$ forge script scripts/DeployDevelopment.s.sol --broadcast --fork-url http://localhost:8545 --private-key $PRIVATE_KEY  --code-size-limit 50000
```

> 我们再次增加了智能合约代码的大小，以防止编译器失败。

`--broadcast` 启用交易广播。默认情况下未启用它，因为并非每个脚本都发送交易。`--fork-url` 设置将交易发送到的节点的地址。`--private-key` 设置发送者钱包：需要私钥来签署交易。你可以选择 Anvil 启动时打印的任何私钥。我选择了第一个：
> 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80

部署需要几秒钟。最后，你将看到它发送的交易列表。它还会将交易收据保存到 `broadcast` 文件夹中。在 Anvil 中，你还将看到许多带有 `eth_sendRawTransaction`、`eth_getTransactionByHash` 和 `eth_getTransactionReceipt` 的行——在将交易发送到 Anvil 之后，Forge 使用 JSON-RPC API 来检查它们的状态并获取交易执行结果（收据）。

恭喜！你刚刚部署了一个智能合约！

## 与合约交互，ABI

现在，让我们看看如何与已部署的合约交互。

每个合约都公开一组公共函数。在池合约的情况下，这些是 `mint(...)` 和 `swap(...)`。此外，Solidity 会为公共变量创建 getter，因此我们也可以调用 `token0()`、`token1()`、`positions()` 等。然而，由于合约是编译后的字节码，**函数名称在编译期间会丢失，并且不会存储在区块链上**。相反，每个函数都由一个选择器标识，该选择器是函数签名的哈希值的前 4 个字节。在伪代码中：
```
hash("transfer(address,address,uint256)")[0:4]
```

> EVM 使用 [Keccak 哈希算法](https://en.wikipedia.org/wiki/SHA-3)，该算法已标准化为 SHA-3。具体来说，Solidity 中的哈希函数是 `keccak256`。

了解了这一点，让我们对已部署的合约进行两次调用：一次是通过 `curl` 进行低级别调用，另一次是使用 `cast` 进行调用。

### 代币余额
让我们检查部署者地址的 WETH 余额。该函数的签名是 `balanceOf(address)`（如 [ERC-20](https://eips.ethereum.org/EIPS/eip-20) 中定义的那样）。要找到此函数的 ID（其选择器），我们将对其进行哈希处理并取前四个字节：
```shell
$ cast keccak "balanceOf(address)"| cut -b 1-10
0x70a08231
```

要传递地址，我们只需将其附加到函数选择器（并添加左侧填充到 32 位数字，因为地址在函数调用数据中占用 32 字节）：
> 0x70a08231000000000000000000000000f39fd6e51aad88f6f4ce6ab8827279cfffb92266

`0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266` 是我们将要检查余额的地址。这是我们的地址，Anvil 中的第一个帐户。

接下来，我们执行 `eth_call` JSON-RPC 方法来进行调用。请注意，这不需要发送交易——此端点用于从合约读取数据。

```shell
$ params='{"from":"0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266","to":"0xe7f1725e7734ce288f8367e1bb143e90bb3f0512","data":"0x70a08231000000000000000000000000f39fd6e51aad88f6f4ce6ab8827279cfffb92266"}'
$ curl -X POST -H 'Content-Type: application/json' \
  --data '{"id":1,"jsonrpc":"2.0","method":"eth_call","params":['"$params"',"latest"]}' \
  http://127.0.0.1:8545
{"jsonrpc":"2.0","id":1,"result":"0x00000000000000000000000000000000000000000000011153ce5e56cf880000"}
```

> “to” 地址是 USDC 代币。它由部署脚本打印，并且在你的情况下可能不同。

Ethereum 节点以原始字节形式返回结果，要解析它们，我们需要知道返回值的类型。在 `balanceOf` 函数的情况下，返回值的类型是 `uint256`。使用 `cast`，我们可以将其转换为十进制数，然后将其转换为 ether：
```shell
$ cast --to-dec 0x00000000000000000000000000000000000000000000011153ce5e56cf880000| cast --from-wei
5042.000000000000000000
```

余额是正确的！我们向我们的地址铸造了 5042 USDC。

### 当前 Tick 和价格

上面的示例是低级别合约调用的演示。通常，你永远不会通过 `curl` 进行调用，而是使用工具或库来简化它。而且 Cast 再次可以帮助我们！

让我们使用 `cast` 获取池的当前价格和 tick：
```shell
$ cast call POOL_ADDRESS "slot0()"| xargs cast --abi-decode "a()(uint160,int24)"
5602277097478614198912276234240
85176
```

太棒了！第一个值是当前的 $\sqrt{P}$，第二个值是当前的 tick。

> 因为 `--abi-decode` 需要完整的函数签名，所以即使我们只想解码函数输出，我们也必须指定 "a()"。

### ABI

为了简化与合约的交互，Solidity 编译器可以输出 ABI，即应用程序二进制接口。

ABI 是一个 JSON 文件，其中包含合约的所有公共方法和事件的描述。此文件的目的是使编码函数参数和解码返回值更容易。要使用 Forge 获取 ABI，请使用以下命令：

```shell
$ forge inspect UniswapV3Pool abi
```

随意浏览该文件以更好地了解其内容。
