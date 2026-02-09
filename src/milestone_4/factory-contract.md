# 工厂合约

Uniswap 的设计假定存在许多离散的 Pool 合约，每个 pool 处理一个 token 对的交换。当我们需要在没有 pool 的两个 token 之间进行交换时，这看起来有些问题——如果没有 pool，则无法进行交换。但是，我们仍然可以进行中间交换：首先交换到与任一 token 都有配对的 token，然后将此 token 交换到目标 token。这可以更深入，并拥有更多的中间 token。然而，手动执行此操作很麻烦，幸运的是，我们可以通过在智能合约中实现它来简化此过程。

Factory 合约是一个具有多种用途的合约：
1. 它充当 Pool 合约的集中注册表。使用 factory，你可以找到所有已部署的 pool、它们的 token 和地址。
2. 它简化了 Pool 合约的部署。EVM 允许从智能合约部署智能合约——Factory 使用此功能使 pool 部署变得轻而易举。
3. 它使 pool 地址可预测，并允许在不调用注册表的情况下计算它们。这使得
pool 易于发现。

让我们构建 Factory 合约！但在执行此操作之前，我们需要学习一些新知识。

## `CREATE` 和 `CREATE2` 操作码

EVM 有两种部署合约的方式：通过 `CREATE` 或通过 `CREATE2` 操作码。它们之间唯一的区别在于生成新合约地址的方式：
1. `CREATE` 使用部署者的帐户 `nonce` 来生成合约地址（伪代码）：
    ```
    KECCAK256(deployer.address, deployer.nonce)
    ```
    `nonce` 是一个特定于帐户的交易计数器。在新合约地址生成中使用 `nonce` 使得在其他合约或链下应用中计算地址变得困难，主要是因为要查找合约部署时的 nonce，需要扫描历史帐户交易。
2. `CREATE2` 使用自定义 *salt* 来生成合约地址。这只是一个由开发者选择的任意字节序列，用于使地址生成具有确定性（并减少冲突的机会）。
    ```
    KECCAK256(deployer.address, salt, contractCodeHash)
    ```

我们需要知道区别，因为 Factory 在部署 Pool 合约时使用 `CREATE2`，因此 pool 获得唯一且确定的地址，这些地址可以在其他合约和链下应用中计算。具体来说，对于 salt，Factory 使用这些 pool 参数计算哈希：
```solidity
keccak256(abi.encodePacked(token0, token1, tickSpacing))
```

`token0` 和 `token1` 是 pool token 的地址，`tickSpacing` 是我们接下来要了解的内容。

## Tick 间距

回顾 `swap` 函数中的循环：
```solidity
while (
    state.amountSpecifiedRemaining > 0 &&
    state.sqrtPriceX96 != sqrtPriceLimitX96
) {
    ...
    (step.nextTick, ) = tickBitmap.nextInitializedTickWithinOneWord(...);
    (state.sqrtPriceX96, step.amountIn, step.amountOut) = SwapMath.computeSwapStep(...);
    ...
}
```

此循环通过在任一方向上迭代来查找具有一些流动性的已初始化 tick。然而，这种迭代是一项昂贵的操作：如果一个 tick 很远，代码将需要传递当前 tick 和目标 tick 之间的所有 tick，这会消耗 gas。为了使此循环更节省 gas，Uniswap pool 具有 `tickSpacing` 设置，顾名思义，它设置了 tick 之间的距离：距离越宽，交换的 gas 效率越高。

但是，tick 间距越宽，精度越低。低波动性对（例如稳定币对）需要更高的精度，因为此类对中的价格变动幅度较小。中度和高波动性对需要较低的精度，因为此类对中的价格变动幅度较大。为了处理这种多样性，Uniswap 允许在部署配对时选择一个 tick 间距。Uniswap 允许部署者从以下选项中选择：10、60 或 200。为简单起见，我们将只有 10 和 60。

从技术上讲，tick 索引只能是 `tickSpacing` 的倍数：如果 `tickSpacing` 为 10，则只有 10 的倍数才能作为有效的 tick 索引（10、20、5000、5010，但不是 8、12、5001 等）。但是，重要的是，这不适用于当前价格——它仍然可以是任何 tick，因为我们希望它尽可能精确。`tickSpacing` 仅适用于价格范围。

因此，每个 pool 都由此参数集唯一标识：
1. `token0`，
2. `token1`，
3. `tickSpacing`；

> 是的，可以存在具有相同 token 但 tick 间距不同的 pool。

Factory 合约使用此参数集作为 pool 的唯一标识符，并将其作为 salt 传递以生成新的 pool 合约地址。

> 从现在开始，我们将假定所有 pool 的 tick 间距为 60，并且我们将对稳定币对使用 10。请注意，只有可被这些值整除的 tick 才能在 ticks 位图中标记为已初始化。例如，当 tick 间距为 60 时，只有 tick -120、-60、0、60、120 等才能被初始化并用于流动性范围。

## 工厂实现

在 Factory 的构造函数中，我们需要初始化支持的 tick 间距：
```solidity
// src/UniswapV3Factory.sol
contract UniswapV3Factory is IUniswapV3PoolDeployer {
    mapping(uint24 => bool) public tickSpacings;
    constructor() {
        tickSpacings[10] = true;
        tickSpacings[60] = true;
    }

    ...
```

> 我们可以将它们设为常量，但我们需要将其作为映射用于以后的里程碑（tick 间距将具有不同的交换费用金额）。

Factory 合约是一个只有一个函数 `createPool` 的合约。该函数首先进行我们在创建 pool 之前需要进行的必要检查：
```solidity
// src/UniswapV3Factory.sol
contract UniswapV3Factory is IUniswapV3PoolDeployer {
    PoolParameters public parameters;
    mapping(address => mapping(address => mapping(uint24 => address)))
        public pools;

    ...

    function createPool(
        address tokenX,
        address tokenY,
        uint24 tickSpacing
    ) public returns (address pool) {
        if (tokenX == tokenY) revert TokensMustBeDifferent();
        if (!tickSpacings[tickSpacing]) revert UnsupportedTickSpacing();

        (tokenX, tokenY) = tokenX < tokenY
            ? (tokenX, tokenY)
            : (tokenY, tokenX);

        if (tokenX == address(0)) revert TokenXCannotBeZero();
        if (pools[tokenX][tokenY][tickSpacing] != address(0))
            revert PoolAlreadyExists();
        
        ...
```

请注意，这是我们第一次对 token 进行排序：
```solidity
(tokenX, tokenY) = tokenX < tokenY
    ? (tokenX, tokenY)
    : (tokenY, tokenX);
```

从现在开始，我们还将期望 pool token 地址已排序，即排序后 `token0` 在 `token1` 之前。我们将强制执行此操作以使 salt（和 pool 地址）计算保持一致。

> 此更改还会影响我们在测试和部署脚本中部署 token 的方式：我们需要确保 WETH 始终是 `token0`，以简化 Solidity 中的价格计算（否则，我们需要使用小数价格，例如 1/5000）。如果 WETH 在你的测试中不是 `token0`，请更改 token 部署的顺序。

之后，我们准备 pool 参数并部署一个 pool：
```solidity
parameters = PoolParameters({
    factory: address(this),
    token0: tokenX,
    token1: tokenY,
    tickSpacing: tickSpacing
});

pool = address(
    new UniswapV3Pool{
        salt: keccak256(abi.encodePacked(tokenX, tokenY, tickSpacing))
    }()
);

delete parameters;
```

这段代码看起来很奇怪，因为没有使用 `parameters`。Uniswap 使用 [控制反转](https://en.wikipedia.org/wiki/Inversion_of_control) 在部署期间将参数传递给 pool。让我们看一下更新后的 Pool 合约构造函数：
```solidity
// src/UniswapV3Pool.sol
contract UniswapV3Pool is IUniswapV3Pool {
    ...
    constructor() {
        (factory, token0, token1, tickSpacing) = IUniswapV3PoolDeployer(
            msg.sender
        ).parameters();
    }
    ..
}
```

啊哈！Pool 期望其部署者实现 `IUniswapV3PoolDeployer` 接口（该接口仅定义了 `parameters()` getter），并在部署期间在构造函数中调用它以获取参数。这是流程的样子：
1. `Factory`：定义 `parameters` 状态变量（实现 `IUniswapV3PoolDeployer`）并在部署 pool 之前设置好。
2. `Factory`：部署一个 pool。
3. `Pool`：在构造函数中，在其部署者上调用 `parameters()` 函数，并期望返回 pool 参数。
4. `Factory`：调用 `delete parameters;` 来清理 `parameters` 状态变量的插槽并减少 gas 消耗。这是一个临时状态变量，仅在调用 `createPool()` 期间具有值。

创建 pool 后，我们将其保留在 `pools` 映射中（以便可以通过其 token 找到它）并发出事件：
```solidity
    pools[tokenX][tokenY][tickSpacing] = pool;
    pools[tokenY][tokenX][tickSpacing] = pool;

    emit PoolCreated(tokenX, tokenY, tickSpacing, pool);
}
```

## Pool 初始化

正如你从上面的代码中注意到的，我们不再在 Pool 的构造函数中设置 `sqrtPriceX96` 和 `tick`——这现在在一个单独的函数 `initialize` 中完成，该函数需要在部署 pool 后调用：

```solidity
// src/UniswapV3Pool.sol
function initialize(uint160 sqrtPriceX96) public {
    if (slot0.sqrtPriceX96 != 0) revert AlreadyInitialized();

    int24 tick = TickMath.getTickAtSqrtRatio(sqrtPriceX96);

    slot0 = Slot0({sqrtPriceX96: sqrtPriceX96, tick: tick});
}
```

所以这就是我们现在部署 pool 的方式：

```solidity
UniswapV3Factory factory = new UniswapV3Factory();
UniswapV3Pool pool = UniswapV3Pool(factory.createPool(token0, token1, tickSpacing));
pool.initialize(sqrtP(currentPrice));
```

## `PoolAddress` 库

现在让我们实现一个库，该库将帮助我们从其他合约计算 pool 合约地址。该库将只有一个函数 `computeAddress`：
```solidity
// src/lib/PoolAddress.sol
library PoolAddress {
    function computeAddress(
        address factory,
        address token0,
        address token1,
        uint24 tickSpacing
    ) internal pure returns (address pool) {
        require(token0 < token1);
        ...
```

该函数需要知道 pool 参数（它们用于构建 salt）和 Factory 合约地址。它期望 token 已排序，正如我们上面讨论的那样。

现在，该函数的核心：
```solidity
pool = address(
    uint160(
        uint256(
            keccak256(
                abi.encodePacked(
                    hex"ff",
                    factory,
                    keccak256(
                        abi.encodePacked(token0, token1, tickSpacing)
                    ),
                    keccak256(type(UniswapV3Pool).creationCode)
                )
            )
        )
    )
);
```

这就是 `CREATE2` 在底层计算新合约地址的方式。让我们解开它：

1. 首先，我们计算 salt (`abi.encodePacked(token0, token1, tickSpacing)`) 并对其进行哈希；
2. 然后，我们获得 Pool 合约代码 (`type(UniswapV3Pool).creationCode`) 并也对其进行哈希；
3. 然后，我们构建一个字节序列，其中包括：`0xff`、Factory 合约地址、哈希 salt 和哈希 Pool 合约代码；
4. 然后，我们对该序列进行哈希并将其转换为地址。

这些步骤实现了合约地址生成，如 [EIP-1014](https://eips.ethereum.org/EIPS/eip-1014) 中定义的那样，该 EIP 添加了 `CREATE2` 操作码。让我们仔细看看构成哈希字节序列的值：
1. 如 EIP 中定义的那样，`0xff` 用于区分由 `CREATE` 和 `CREATE2` 生成的地址；
2. `factory` 是部署者的地址，在我们的例子中是 Factory 合约；
3. salt 之前讨论过——它唯一地标识一个 pool；
4. 需要哈希合约代码以防止冲突：不同的合约可以具有相同的 salt，但它们的代码
哈希将不同。

因此，根据此方案，合约地址是唯一标识该合约的值的哈希，包括其部署者、代码和唯一参数。我们可以从任何地方使用此函数来查找 pool 地址，而无需进行任何外部调用，也无需查询 factory。

## Manager 和 Quoter 的简化接口

在 Manager 和 Quoter 合约中，我们不再需要向用户询问 pool 地址了！这使得与合约的交互更加容易，因为用户不需要知道 pool 地址，他们只需要知道 token。但是，用户还需要指定 tick 间距，因为它包含在 pool 的 salt 中。

此外，我们不再需要向用户询问 `zeroForOne` 标志，因为我们现在可以始终通过 token 排序来弄清楚它。当“from token”小于“to token”时，`zeroForOne` 为 true，因为 pool 的 `token0` 始终小于 `token1`。同样，当“from token”大于“to token”时，`zeroForOne` 始终为 false。

> 地址是哈希，哈希是数字，所以我们在比较地址时可以说“小于”或“大于”。
