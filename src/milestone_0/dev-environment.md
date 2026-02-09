# 开发环境

我们将构建两个应用程序：

1. 一个链上应用：部署在 Ethereum 上的智能合约集合。
2. 一个链下应用：一个与智能合约交互的前端应用程序。

虽然前端应用程序的开发是本书的一部分，但它不会是我们的主要重点。我们将仅仅构建它来演示智能合约如何与前端应用程序集成。因此，前端应用程序是可选的，但我仍然会提供代码。

## Ethereum 快速入门

Ethereum 是一个允许任何人在其上运行应用程序的区块链。它可能看起来像一个云提供商，但存在多个差异：
1. 您无需为托管您的应用程序付费。但您需要为部署付费。
2. 您的应用程序是不可变的。也就是说：部署后您将无法修改它。
3. 用户将付费使用您的应用程序。

为了更好地理解这些时刻，让我们看看 Ethereum 是由什么构成的。

Ethereum（以及任何其他区块链）的核心是一个数据库。Ethereum 数据库中最有价值的数据是*账户状态*。账户是一个带有相关数据的 Ethereum 地址：

1. 余额：账户的以太币余额。
2. 代码：部署在此地址的智能合约的字节码。
3. 存储：智能合约用于存储数据的空间。
4. Nonce：一个用于防止重放攻击的序列整数。

Ethereum 的主要工作是以安全的方式构建和维护这些数据，不允许未经授权的访问。

Ethereum 也是一个网络，一个由计算机组成的网络，它们彼此独立地构建和维护状态。网络的主要目标是**去中心化对数据库的访问**：必须没有任何一个可以单方面修改数据库中任何内容的权威机构。这是通过*共识*实现的，这是一组网络中所有节点都遵循的规则。如果一方决定滥用规则，它将被排除在网络之外。

> 有趣的事实：区块链可以使用 MySQL！除了性能之外，没有什么可以阻止这一点。反过来，Ethereum 使用 [LevelDB](https://github.com/google/leveldb)，一个快速的键值数据库。

每个 Ethereum 节点也运行 EVM，Ethereum 虚拟机。虚拟机是一个可以运行其他程序的程序，EVM 是一个执行智能合约的程序。用户通过交易与合约交互：除了简单地发送以太币，交易还可以包含智能合约调用数据。它包括：

1. 一个编码的合约函数名称。
2. 函数参数。

交易被打包在区块中，然后区块被矿工挖掘。网络中的每个参与者都可以验证任何交易和任何区块。

从某种意义上说，智能合约类似于 JSON API，但您调用的是智能合约函数而不是端点，并且您提供函数参数。与 API 后端类似，智能合约执行编程逻辑，可以选择性地修改智能合约存储。与 JSON API 不同，您需要发送交易来改变区块链状态，并且您需要为发送的每笔交易付费。

最后，Ethereum 节点公开一个 JSON-RPC API。通过这个 API，我们可以与节点交互来：获取帐户余额、估算 gas 成本、获取区块和交易、发送交易，以及执行合约调用而不发送交易（这用于从智能合约中读取数据）。[这里](https://eth.wiki/json-rpc/API) 你可以找到可用端点的完整列表。

> 交易也通过 JSON-RPC API 发送，参见 [eth_sendTransaction](https://ethereum.org/en/developers/docs/apis/json-rpc/#eth_sendtransaction)。

## 本地开发环境

如今，使用了多种智能合约开发环境：
1. [Truffle](https://trufflesuite.com)
2. [Hardhat](https://hardhat.org)
3. [Foundry](https://github.com/foundry-rs/foundry)

Truffle 是这三者中最古老的，也是最不受欢迎的。Hardhat 是其改进后的后代，也是使用最广泛的工具。Foundry 是一个新的项目，它带来了对测试的不同看法。

虽然 HardHat 仍然是一个流行的解决方案，但越来越多的项目正在转向 Foundry。这有很多原因：
1. 使用 Foundry，我们可以用 Solidity 编写测试。这更加方便，因为我们不需要在 JavaScript（Truffle 和 HardHat 使用 JS 进行测试和自动化）和 Solidity 之间切换。用 Solidity 编写测试更加方便，因为你拥有所有原生功能（例如，你不需要一个特殊的类型来表示大数字，也不需要在字符串和 [BigNumber](https://docs.ethers.io/v5/api/utils/bignumber/) 之间进行转换）。
2. Foundry 在测试期间不运行节点。这使得测试和迭代功能更快！无论何时你运行测试，Truffle 和 HardHat 都会启动一个节点；Foundry 在一个内部的 EVM 上执行测试。

话虽如此，我们将使用 Foundry 作为我们主要的智能合约开发和测试工具。

### Foundry

[Foundry](https://github.com/foundry-rs/foundry) 是一套用于 Ethereum 应用程序开发的工具。具体来说，我们将使用：
1. [Forge](https://github.com/foundry-rs/foundry/tree/master/forge)，一个用于 Solidity 的测试框架。
2. [Anvil](https://github.com/foundry-rs/foundry/tree/master/anvil)，一个专为使用 Forge 开发而设计的本地 Ethereum 节点。我们将使用它来将我们的合约部署到本地节点，并通过前端应用程序连接到它。
3. [Cast](https://github.com/foundry-rs/foundry/tree/master/cast)，一个具有大量有用功能的 CLI 工具。

Forge 使智能合约开发者的生活更加轻松。使用 Forge，我们不需要运行本地节点来测试合约。相反，Forge 在其内部 EVM 上运行测试，这更快，并且不需要发送交易和挖掘区块。

Forge 允许我们用 Solidity 编写测试！Forge 还使模拟区块链状态变得更容易：我们可以轻松地伪造我们的以太币或 token 余额，从其他地址执行合约，在任何地址部署任何合约，等等。

但是，我们仍然需要一个本地节点来部署我们的合约。为此，我们将使用 Anvil。前端应用程序使用 JavaScript Web3 库与 Ethereum 节点交互（发送交易、查询状态、预估交易 gas 成本等）——这就是为什么我们需要运行一个本地节点。

### Ethers.js

[Ethers.js](https://github.com/ethers-io/ethers.js/) 是一组用 JavaScript 编写的 Ethereum 实用程序。这是去中心化应用程序开发中使用的两个最流行的 JavaScript 库之一（另一个是 [web3.js](https://github.com/ChainSafe/web3.js)）。这些库允许我们通过 JSON-API 与 Ethereum 节点交互，并且它们带有多个实用函数，使开发者的生活更加轻松。

### MetaMask

[MetaMask](https://metamask.io/) 是浏览器中的一个 Ethereum 钱包。它是一个浏览器扩展，可以创建并安全地存储私钥。MetaMask 是数百万用户使用的主要 Ethereum 钱包应用程序。我们将使用它来签署我们将发送到本地节点的交易。

### React

[React](https://reactjs.org/) 是一个众所周知的 JavaScript 库，用于构建前端应用程序。您不需要了解 React，我将提供一个模板应用程序。

## 设置项目

要设置项目，创建一个新文件夹并在其中运行 `forge init`：
```shell
$ mkdir uniswapv3clone
$ cd uniswapv3clone
$ forge init
```

> 如果你使用 Visual Studio Code，添加 `--vscode` 标记到 `forge init`：`forge init --vscode`。Forge 将使用 VSCode 特定的设置初始化项目。

Forge 将在 `src`、`test` 和 `script` 文件夹中创建示例合约——这些可以被移除。

要设置前端应用程序：
```shell
$ npx create-react-app ui
```

它位于一个子文件夹中，因此文件夹名称之间没有冲突。
