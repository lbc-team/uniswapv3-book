# 多池交易

我们现在进入本里程碑的核心——在我们的合约中实现多池交易。在本里程碑中，我们不会触及 Pool 合约，因为它是一个核心合约，应该只实现核心功能。多池交易是一个实用功能，我们将在 Manager 和 Quoter 合约中实现它。

## 更新 Manager 合约

### 单池和多池交易
在我们当前的实现中，Manager 合约中的 `swap` 函数仅支持单池交易，并在参数中接收池地址：

```solidity
function swap(
    address poolAddress_,
    bool zeroForOne,
    uint256 amountSpecified,
    uint160 sqrtPriceLimitX96,
    bytes calldata data
) public returns (int256, int256) { ... }
```

我们将把它分成两个函数：单池交易和多池交易。这些函数将有不同的参数集：

```solidity
struct SwapSingleParams {
    address tokenIn;
    address tokenOut;
    uint24 tickSpacing;
    uint256 amountIn;
    uint160 sqrtPriceLimitX96;
}

struct SwapParams {
    bytes path;
    address recipient;
    uint256 amountIn;
    uint256 minAmountOut;
}
```

1. `SwapSingleParams` 接收池参数、输入数量和一个限制价格——这与我们之前的非常相似。请注意，不再需要 `data`。
2. `SwapParams` 接收路径、输出数量接收者、输入数量和最小输出数量。后一个参数取代了 `sqrtPriceLimitX96`，因为在进行多池交易时，我们不能使用来自 Pool 合约的滑点保护（它使用限制价格）。我们需要实现另一个滑点保护，它检查最终输出数量并将其与 `minAmountOut` 进行比较：当最终输出数量小于 `minAmountOut` 时，滑点保护失败。

### 核心交易逻辑

让我们实现一个内部函数 `_swap`，它将被单池和多池交易函数调用。它将准备参数并调用 `Pool.swap`。

```solidity
function _swap(
    uint256 amountIn,
    address recipient,
    uint160 sqrtPriceLimitX96,
    SwapCallbackData memory data
) internal returns (uint256 amountOut) {
    ...
```

`SwapCallbackData` 是一个新的数据结构，包含我们在交易函数和 `uniswapV3SwapCallback` 之间传递的数据：
```solidity
struct SwapCallbackData {
    bytes path;
    address payer;
}
```

`path` 是交易路径，`payer` 是在交易中提供输入 token 的地址——在多池交易期间，我们将有不同的付款人。

我们在 `_swap` 中做的第一件事是使用 `Path` 库提取池参数：

```solidity
// function _swap(...) {
(address tokenIn, address tokenOut, uint24 tickSpacing) = data
    .path
    .decodeFirstPool();
```

然后我们确定交易方向：

```solidity
bool zeroForOne = tokenIn < tokenOut;
```

然后我们进行实际的交易：
```solidity
// function _swap(...) {
(int256 amount0, int256 amount1) = getPool(
    tokenIn,
    tokenOut,
    tickSpacing
).swap(
        recipient,
        zeroForOne,
        amountIn,
        sqrtPriceLimitX96 == 0
            ? (
                zeroForOne
                    ? TickMath.MIN_SQRT_RATIO + 1
                    : TickMath.MAX_SQRT_RATIO - 1
            )
            : sqrtPriceLimitX96,
        abi.encode(data)
    );
```

这部分与我们之前的相同，但这次我们调用 `getPool` 来查找池。`getPool` 是一个对 token 进行排序并调用 `PoolAddress.computeAddress` 的函数：

```solidity
function getPool(
    address token0,
    address token1,
    uint24 tickSpacing
) internal view returns (IUniswapV3Pool pool) {
    (token0, token1) = token0 < token1
        ? (token0, token1)
        : (token1, token0);
    pool = IUniswapV3Pool(
        PoolAddress.computeAddress(factory, token0, token1, tickSpacing)
    );
}
```

完成交易后，我们需要确定哪个数量是输出数量：
```solidity
// function _swap(...) {
amountOut = uint256(-(zeroForOne ? amount1 : amount0));
```

就是这样。现在让我们看看单池交易是如何进行的。

### 单池交易

`swapSingle` 仅作为 `_swap` 的包装器：

```solidity
function swapSingle(SwapSingleParams calldata params)
    public
    returns (uint256 amountOut)
{
    amountOut = _swap(
        params.amountIn,
        msg.sender,
        params.sqrtPriceLimitX96,
        SwapCallbackData({
            path: abi.encodePacked(
                params.tokenIn,
                params.tickSpacing,
                params.tokenOut
            ),
            payer: msg.sender
        })
    );
}
```

请注意，我们在这里构建了一个单池路径：单池交易是只有一个池的多池交易 🙂。

### 多池交易

多池交易仅比单池交易稍微困难一些。让我们来看看：

```solidity
function swap(SwapParams memory params) public returns (uint256 amountOut) {
    address payer = msg.sender;
    bool hasMultiplePools;
    ...
```

第一笔交易由用户支付，因为是用户提供输入 token。

然后，我们开始迭代路径中的池：

```solidity
...
while (true) {
    hasMultiplePools = params.path.hasMultiplePools();

    params.amountIn = _swap(
        params.amountIn,
        hasMultiplePools ? address(this) : params.recipient,
        0,
        SwapCallbackData({
            path: params.path.getFirstPool(),
            payer: payer
        })
    );
    ...
```

在每次迭代中，我们都使用以下参数调用 `_swap`：
1. `params.amountIn` 跟踪输入数量。在第一次交易期间，它是用户提供的数量。在接下来的交易中，它是从先前交易返回的数量。
2. `hasMultiplePools ? address(this) : params.recipient`——如果路径中有多个池，则接收者是 Manager 合约，它将在交易之间存储 token。如果路径中只有一个池（最后一个池），则接收者是参数中指定的接收者（通常是发起交易的同一用户）。
3. `sqrtPriceLimitX96` 设置为 0，以禁用 Pool 合约中的滑点保护。
4. 最后一个参数是我们传递给 `uniswapV3SwapCallback` 的——我们稍后会看到它。

完成一次交易后，我们需要继续路径中的下一个池或返回：
```solidity
    ...

    if (hasMultiplePools) {
        payer = address(this);
        params.path = params.path.skipToken();
    } else {
        amountOut = params.amountIn;
        break;
    }
}
```

这是我们更改付款人并从路径中删除已处理池的地方。

最后，新的滑点保护：

```solidity
if (amountOut < params.minAmountOut)
    revert TooLittleReceived(amountOut);
```

### 交易回调

让我们看一下更新后的交易回调：

```solidity
function uniswapV3SwapCallback(
    int256 amount0,
    int256 amount1,
    bytes calldata data_
) public {
    SwapCallbackData memory data = abi.decode(data_, (SwapCallbackData));
    (address tokenIn, address tokenOut, ) = data.path.decodeFirstPool();

    bool zeroForOne = tokenIn < tokenOut;

    int256 amount = zeroForOne ? amount0 : amount1;

    if (data.payer == address(this)) {
        IERC20(tokenIn).transfer(msg.sender, uint256(amount));
    } else {
        IERC20(tokenIn).transferFrom(
            data.payer,
            msg.sender,
            uint256(amount)
        );
    }
}
```

回调期望使用路径和付款人地址编码的 `SwapCallbackData`。它从路径中提取池 token，确定交易方向（`zeroForOne`）以及合约需要转出的数量。然后，它根据付款人地址采取不同的行动：
1. 如果付款人是当前合约（在进行连续交易时是这样），它会将 token 从当前合约的余额转移到下一个池（调用此回调的池）。
2. 如果付款人是不同的地址（发起交易的用户），它会将 token 从用户的余额中转移。

## 更新 Quoter 合约

Quoter 是另一个需要更新的合约，因为我们希望使用它来查找多池交易中的输出数量。与 Manager 类似，我们将有两个版本的 `quote` 函数：单池和多池函数。让我们首先看一下前者。

### 单池报价
我们只需要对当前的 `quote` 实现进行一些更改：
1. 将其重命名为 `quoteSingle`；
2.  将参数提取到一个结构中（这主要是一个美观上的改变）；
3.  在参数中，使用两个 token 地址和一个 tick 间距来代替池地址。

```solidity
// src/UniswapV3Quoter.sol
struct QuoteSingleParams {
    address tokenIn;
    address tokenOut;
    uint24 tickSpacing;
    uint256 amountIn;
    uint160 sqrtPriceLimitX96;
}

function quoteSingle(QuoteSingleParams memory params)
    public
    returns (
        uint256 amountOut,
        uint160 sqrtPriceX96After,
        int24 tickAfter
    )
{
    ...
```

我们在函数主体中唯一的更改是使用 `getPool` 来查找池地址：
```solidity
    ...
    IUniswapV3Pool pool = getPool(
        params.tokenIn,
        params.tokenOut,
        params.tickSpacing
    );

    bool zeroForOne = params.tokenIn < params.tokenOut;
    ...
```

### 多池报价

多池报价实现类似于多池交易实现，但它使用的参数更少。

```solidity
function quote(bytes memory path, uint256 amountIn)
    public
    returns (
        uint256 amountOut,
        uint160[] memory sqrtPriceX96AfterList,
        int24[] memory tickAfterList
    )
{
    sqrtPriceX96AfterList = new uint160[](path.numPools());
    tickAfterList = new int24[](path.numPools());
    ...
```

作为参数，我们只需要输入数量和交易路径。该函数返回与 `quoteSingle` 类似的值，但“交易后的价格”和“交易后的 tick”是在每次交易后收集的，因此我们需要返回数组。

```solidity
uint256 i = 0;
while (true) {
    (address tokenIn, address tokenOut, uint24 tickSpacing) = path
        .decodeFirstPool();

    (
        uint256 amountOut_,
        uint160 sqrtPriceX96After,
        int24 tickAfter
    ) = quoteSingle(
            QuoteSingleParams({
                tokenIn: tokenIn,
                tokenOut: tokenOut,
                tickSpacing: tickSpacing,
                amountIn: amountIn,
                sqrtPriceLimitX96: 0
            })
        );

    sqrtPriceX96AfterList[i] = sqrtPriceX96After;
    tickAfterList[i] = tickAfter;
    amountIn = amountOut_;
    i++;

    if (path.hasMultiplePools()) {
        path = path.skipToken();
    } else {
        amountOut = amountIn;
        break;
    }
}
```

循环的逻辑与更新后的 `swap` 函数中的逻辑相同：
1. 获取当前池的参数；
2. 在当前池上调用 `quoteSingle`；
3. 保存返回值；
4. 如果路径中有更多池，则重复，否则返回。
