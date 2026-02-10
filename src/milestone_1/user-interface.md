# 用户界面

终于，我们到达了此里程碑的最后一站——构建用户界面！

![UI应用程序的界面](https://img.learnblockchain.cn/how_to_defi/uniswapv3/src/milestone_1/images/ui.png)

由于构建前端应用程序不是本书的主要目标，因此我不会展示如何从头开始构建这样的应用程序。相反，我将展示如何使用 MetaMask 与智能合约交互。

> 如果你想尝试该应用程序并在本地运行它，你可以在代码仓库的 [ui](https://github.com/Jeiwan/uniswapv3-code/tree/milestone_1/ui) 文件夹中找到它。这是一个简单的 React 应用程序，要在本地运行它，请在 `App.js` 中设置合约地址并运行 `yarn start`。

## 工具概述

### 什么是 MetaMask？

MetaMask 是一个作为浏览器扩展实现的以太坊钱包。 它创建并存储私钥、显示代币余额、允许连接到不同的网络，并发送和接收以太币和代币——一个钱包必须做的所有事情。

除此之外，MetaMask 充当签名者和提供者。 作为提供者，它连接到以太坊节点并提供一个接口来使用其 JSON-RPC API。 作为签名者，它提供了一个用于安全交易签名的接口，因此它可用于使用钱包中的私钥签署任何交易。

![MetaMask 如何工作](https://img.learnblockchain.cn/how_to_defi/uniswapv3/src/milestone_1/images/metamask.png)

### 便捷库

然而，MetaMask 并没有提供太多的功能：它只能管理账户和发送原始交易。 我们需要另一个库来简化与合约的交互。 我们还需要一组实用程序，这将使我们在处理 EVM 特定的数据（ABI 编码/解码，大数处理等）时更轻松。

有多个这样的库。 其中两个最受欢迎的是：[web3.js](https://github.com/ChainSafe/web3.js) 和 [ethers.js](https://github.com/ethers-io/ethers.js/)。 选择哪一个取决于个人喜好。 对我来说，Ethers.js 似乎有一个更清晰的合约交互界面，所以我选择它。

## 工作流程

现在让我们看看如何使用 MetaMask + Ethers.js 实现交互场景。

### 连接到本地节点

为了发送交易和获取区块链数据，MetaMask 连接到以太坊节点。 为了与我们的合约交互，我们需要连接到本地 Anvil 节点。 为此，打开 MetaMask，点击网络列表，点击“添加网络”，然后添加一个 RPC URL 为 `http://localhost:8545` 的网络。 它会自动检测链 ID（在 Anvil 的情况下为 31337）。

连接到本地节点后，我们需要导入我们的私钥。 在 MetaMask 中，点击地址列表，点击“导入账户”，然后粘贴你之前部署合约时选择的地址的私钥。 之后，转到资产列表并导入两个代币的地址。 现在你应该在 MetaMask 中看到代币的余额。

> MetaMask 仍然存在一些问题。 我遇到的一个问题是，当连接到 `localhost` 时，它会缓存区块链状态。 因此，当重新启动节点时，你可能会看到旧的代币余额和状态。 要解决此问题，请转到高级设置并点击“重置帐户”。 每次重新启动节点后，你都需要执行此操作。

### 连接到 MetaMask

并非每个网站都被允许访问你在 MetaMask 中的地址。 网站首先需要连接到 MetaMask。 当新网站连接到 MetaMask 时，你将看到一个窗口，要求你提供权限。

以下是从前端应用程序连接到 MetaMask 的方法：
```js
// ui/src/contexts/MetaMask.js
const connect = () => {
  if (typeof (window.ethereum) === 'undefined') {
    return setStatus('not_installed');
  }

  Promise.all([
    window.ethereum.request({ method: 'eth_requestAccounts' }),
    window.ethereum.request({ method: 'eth_chainId' }),
  ]).then(function ([accounts, chainId]) {
    setAccount(accounts[0]);
    setChain(chainId);
    setStatus('connected');
  })
    .catch(function (error) {
      console.error(error)
    });
}
```

`window.ethereum` 是 MetaMask 提供的对象，它是与 MetaMask 通信的接口。 如果未定义，则表示未安装 MetaMask。 如果已定义，我们可以向 MetaMask 发送两个请求：`eth_requestAccounts` 和 `eth_chainId`。 实际上，`eth_requestAccounts` 将网站连接到 MetaMask。 它从 MetaMask 查询一个地址，MetaMask 会向用户请求权限。 用户将能够选择要授予访问权限的地址。

`eth_chainId` 将请求 MetaMask 连接的节点的链 ID。 在获得地址和链 ID 之后，最好在界面中显示它们：

![MetaMask 已连接](https://img.learnblockchain.cn/how_to_defi/uniswapv3/src/milestone_1/images/ui_metamask_connected.png)

### 提供流动性

为了将流动性提供给池子，我们需要构建一个表单，要求用户输入他们想要存入的数量。 点击“提交”后，应用程序将构建一个交易，该交易调用 manager 合约中的 `mint`，并提供用户选择的数量。 让我们看看如何做到这一点。

Ether.js 提供了 `Contract` 接口来与合约交互。 这让我们的生活变得更加轻松，因为它承担了编码函数参数、创建有效交易并将其移交给 MetaMask 的工作。 对于我们来说，调用合约就像调用 JS 对象上的异步方法一样。

让我们看看如何创建 `Contracts` 的实例：

```js
token0 = new ethers.Contract(
  props.config.token0Address,
  props.config.ABIs.ERC20,
  new ethers.providers.Web3Provider(window.ethereum).getSigner()
);
```

`Contract` 实例是一个地址和部署在此地址的合约的 ABI。 需要 ABI 才能与合约交互。 第三个参数是 MetaMask 提供的签名者接口——JS 合约实例使用它通过 MetaMask 签署交易。

现在，让我们添加一个向池子添加流动性的函数：
```js
const addLiquidity = (account, { token0, token1, manager }, { managerAddress, poolAddress }) => {
  const amount0 = ethers.utils.parseEther("0.998976618347425280");
  const amount1 = ethers.utils.parseEther("5000"); // 5000 USDC
  const lowerTick = 84222;
  const upperTick = 86129;
  const liquidity = ethers.BigNumber.from("1517882343751509868544");
  const extra = ethers.utils.defaultAbiCoder.encode(
    ["address", "address", "address"],
    [token0.address, token1.address, account]
  );
  ...
```

首先要做的是准备参数。 我们使用之前计算的相同值。

接下来，我们允许 manager 合约获取我们的代币。 首先，我们检查当前的授权额度：
```js
Promise.all(
  [
    token0.allowance(account, managerAddress),
    token1.allowance(account, managerAddress)
  ]
)
```

然后，我们检查其中任何一个是否足以转移相应数量的代币。 如果没有，我们将发送一个 `approve` 交易，该交易要求用户批准向 manager 合约支付特定金额。 在确保用户已批准全额金额后，我们调用 `manager.mint` 以增加流动性：
```js
.then(([allowance0, allowance1]) => {
  return Promise.resolve()
    .then(() => {
      if (allowance0.lt(amount0)) {
        return token0.approve(managerAddress, amount0).then(tx => tx.wait())
      }
    })
    .then(() => {
      if (allowance1.lt(amount1)) {
        return token1.approve(managerAddress, amount1).then(tx => tx.wait())
      }
    })
    .then(() => {
      return manager.mint(poolAddress, lowerTick, upperTick, liquidity, extra)
        .then(tx => tx.wait())
    })
    .then(() => {
      alert('Liquidity added!');
    });
})
```

> `lt` 是 [BigNumber](https://docs.ethers.io/v5/api/utils/bignumber/) 的一个方法。 Ethers.js 使用 BigNumber 来表示 `uint256` 类型，JavaScript 对此 [没有足够的精度](https://docs.ethers.io/v5/api/utils/bignumber/#BigNumber--notes-safenumbers)。 这是我们想要一个方便的库的原因之一。

除了授权额度部分之外，这与测试合约非常相似。

上面代码中的 `token0`、`token1` 和 `manager` 是 `Contract` 的实例。 `approve` 和 `mint` 是合约函数，它们是从我们实例化合约时提供的 ABI 动态生成的。 当调用这些方法时，Ethers.js：
1. 对函数参数进行编码；
2. 构建交易；
3. 将交易传递给 MetaMask 并要求对其进行签名； 用户会看到一个 MetaMask 窗口并按下“确认”；
4. 将交易发送到 MetaMask 连接的节点；
5. 返回一个交易对象，其中包含有关已发送交易的完整信息。

交易对象还包含 `wait` 函数，我们调用该函数以等待交易被挖掘——这允许我们在发送另一个交易之前等待交易成功执行。

> 以太坊需要严格的交易顺序。 还记得 nonce 吗？ 它是此帐户发送的交易的帐户范围索引。 每个新交易都会增加此索引，并且以太坊不会挖掘交易，直到先前的交易（nonce 较小的交易）被挖掘为止。

### 交换代币

要交换代币，我们使用相同的模式：从用户那里获取参数，检查授权额度，并在 manager 上调用 `swap`。

```js
const swap = (amountIn, account, { tokenIn, manager, token0, token1 }, { managerAddress, poolAddress }) => {
  const amountInWei = ethers.utils.parseEther(amountIn);
  const extra = ethers.utils.defaultAbiCoder.encode(
    ["address", "address", "address"],
    [token0.address, token1.address, account]
  );

  tokenIn.allowance(account, managerAddress)
    .then((allowance) => {
      if (allowance.lt(amountInWei)) {
        return tokenIn.approve(managerAddress, amountInWei).then(tx => tx.wait())
      }
    })
    .then(() => {
      return manager.swap(poolAddress, extra).then(tx => tx.wait())
    })
    .then(() => {
      alert('Swap succeeded!');
    }).catch((err) => {
      console.error(err);
      alert('Failed!');
    });
}
```

这里唯一的新内容是 `ethers.utils.parseEther()` 函数，我们用它将数字转换为 wei，这是以太坊中最小的单位。

### 订阅变更

对于去中心化应用程序，反映当前的区块链状态非常重要。 例如，在去中心化交易所的情况下，根据当前的池储备正确计算交换价格至关重要； 过时的数据可能会导致滑点并导致交换交易失败。

在开发池合约时，我们了解了事件，这些事件充当区块链数据索引：每当修改智能合约状态时，最好发出一个事件，因为事件会被索引以进行快速搜索。 我们现在要做的是订阅合约事件，以保持我们的前端应用程序更新。 让我们构建一个事件提要！

如果您像我之前建议的那样检查了 ABI 文件，您会看到它还包含事件的描述：事件名称及其字段。 好吧，[Ether.js 解析它们](https://docs.ethers.io/v5/api/contract/contract/#Contract--events) 并提供了一个接口来订阅新事件。 让我们看看它是如何工作的。

要订阅事件，我们将使用 `on(EVENT_NAME, handler)` 函数。 回调接收事件的所有字段以及事件本身作为参数：
```js
const subscribeToEvents = (pool, callback) => {
  pool.on("Mint", (sender, owner, tickLower, tickUpper, amount, amount0, amount1, event) => callback(event));
  pool.on("Swap", (sender, recipient, amount0, amount1, sqrtPriceX96, liquidity, tick, event) => callback(event));
}
```

要过滤和获取以前的事件，我们可以使用 `queryFilter`：
```js
Promise.all([
  pool.queryFilter("Mint", "earliest", "latest"),
  pool.queryFilter("Swap", "earliest", "latest"),
]).then(([mints, swaps]) => {
  ...
});
```

您可能已经注意到某些事件字段标记为 `indexed`——此类字段由以太坊节点索引，这允许通过此类字段中的特定值搜索事件。 例如，`Swap` 事件具有索引的 `sender` 和 `recipient` 字段，因此我们可以按交换发送者和接收者进行搜索。 同样，Ethere.js 使这更容易：
```js
const swapFilter = pool.filters.Swap(sender, recipient);
const swaps = await pool.queryFilter(swapFilter, fromBlock, toBlock);
```

---

就这样！ 我们完成了里程碑 1！

<p style="font-size:3rem; text-align: center">
🎉🍾🍾🍾🎉
</p>
