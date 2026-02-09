# 滑点保护

滑点是去中心化交易所中一个非常重要的问题。滑点简单来说就是你在初始化交易时在屏幕上看到的价格与交易执行时的实际价格之间的差异。这种差异的出现是因为从你发送交易到它被确认之间有一个短暂的（有时很长，取决于网络拥塞和 gas 成本）延迟。更专业地说，区块链状态每个区块都会变化，并且不能保证你的交易会在特定的区块上应用。

滑点保护解决的另一个重要问题是*三明治攻击*——这是一种针对去中心化交易所用户的常见攻击类型。在三明治攻击期间，攻击者将你的 swap 交易“包裹”在他们的两个交易中：一个在你的交易之前，另一个在你的交易之后。在第一个交易中，攻击者修改池的状态，使你的 swap 对你来说非常不划算，但对攻击者来说却有利可图。这是通过调整池的流动性来实现的，以便你的交易以较低的价格发生。在第二个交易中，攻击者重新建立池的流动性和价格。结果，由于价格被操纵，你获得的 token 比预期少得多，而攻击者则获得了一些利润。

![三明治攻击](images/sandwich_attack.png)

在去中心化交易所中，滑点保护的实现方式是让用户选择允许实际价格下降的幅度。默认情况下，Uniswap V3 将滑点容忍度设置为 0.1%，这意味着只有在执行时的价格不小于用户在浏览器中看到的价格的 99.9% 时，才会执行 swap。这是一个非常严格的范围，用户可以调整这个数字，这在波动性较高时很有用。

让我们将滑点保护添加到我们的实现中！

## Swaps 中的滑点保护

为了保护 swaps，我们需要向 `swap` 函数添加一个参数——我们希望让用户选择一个停止价格，即停止 swapping 的价格。我们将该参数称为 `sqrtPriceLimitX96`：

```solidity
function swap(
    address recipient,
    bool zeroForOne,
    uint256 amountSpecified,
    uint160 sqrtPriceLimitX96,
    bytes calldata data
) public returns (int256 amount0, int256 amount1) {
    ...
    if (
        zeroForOne
            ? sqrtPriceLimitX96 > slot0_.sqrtPriceX96 ||
                sqrtPriceLimitX96 < TickMath.MIN_SQRT_RATIO
            : sqrtPriceLimitX96 < slot0_.sqrtPriceX96 &&
                sqrtPriceLimitX96 > TickMath.MAX_SQRT_RATIO
    ) revert InvalidPriceLimit();
    ...
```

当出售 token $x$（`zeroForOne` 为 true）时，`sqrtPriceLimitX96` 必须介于当前价格和最小 $\sqrt{P}$ 之间，因为出售 token $x$ 会降低价格。同样，当出售 token $y$ 时，`sqrtPriceLimitX96` 必须介于当前价格和最大 $\sqrt{P}$ 之间，因为这会提高价格。

在 while 循环中，我们希望满足两个条件：完整的 swap 数量尚未填满，并且当前价格不等于 `sqrtPriceLimitX96`：
```solidity
..
while (
    state.amountSpecifiedRemaining > 0 &&
    state.sqrtPriceX96 != sqrtPriceLimitX96
) {
...
```

这意味着当达到滑点容忍度时，Uniswap V3 池不会失败，而是简单地部分执行 swap。

我们需要考虑 `sqrtPriceLimitX96` 的另一个地方是在调用 `SwapMath.computeSwapStep` 时：

```solidity
(state.sqrtPriceX96, step.amountIn, step.amountOut) = SwapMath
    .computeSwapStep(
        state.sqrtPriceX96,
        (
            zeroForOne
                ? step.sqrtPriceNextX96 < sqrtPriceLimitX96
                : step.sqrtPriceNextX96 > sqrtPriceLimitX96
        )
            ? sqrtPriceLimitX96
            : step.sqrtPriceNextX96,
        state.liquidity,
        state.amountSpecifiedRemaining
    );
```

在这里，我们要确保 `computeSwapStep` 永远不会计算 `sqrtPriceLimitX96` 之外的 swap 数量——这保证了当前价格永远不会超过限制价格。

## Minting 中的滑点保护

添加流动性也需要滑点保护。这是因为在添加流动性时价格不能改变（流动性必须与当前价格成正比），因此流动性提供者也会受到滑点的影响。但是，与 `swap` 函数不同，我们没有被迫在 Pool 合约中实现滑点保护——回想一下，Pool 合约是一个核心合约，我们不想在其中放入不必要的逻辑。这就是我们创建 Manager 合约的原因，我们将在 Manager 合约中实现滑点保护。

Manager 合约是一个包装合约，使调用 Pool 合约更加方便。为了在 `mint` 函数中实现滑点保护，我们可以简单地检查 Pool 提取的 token 数量，并将它们与用户选择的最小数量进行比较。此外，我们可以让用户免于计算 $\sqrt{P_{lower}}$ 和 $\sqrt{P_{upper}}$ 以及流动性，并在 `Manager.mint()` 中计算这些。

我们更新后的 `mint` 函数现在将采用更多参数，因此让我们将它们分组到一个结构体中：
```solidity
// src/UniswapV3Manager.sol
contract UniswapV3Manager {
    struct MintParams {
        address poolAddress;
        int24 lowerTick;
        int24 upperTick;
        uint256 amount0Desired;
        uint256 amount1Desired;
        uint256 amount0Min;
        uint256 amount1Min;
    }

    function mint(MintParams calldata params)
        public
        returns (uint256 amount0, uint256 amount1)
    {
        ...
```

`amount0Min` 和 `amount1Min` 是根据滑点容忍度计算出的数量。它们必须小于期望的数量，缺口由滑点容忍度设置控制。流动性提供者期望提供的数量不小于 `amount0Min` 和 `amount1Min`。

接下来，我们计算 $\sqrt{P_{lower}}$、$\sqrt{P_{upper}}$ 和流动性：
```solidity
...
IUniswapV3Pool pool = IUniswapV3Pool(params.poolAddress);

(uint160 sqrtPriceX96, ) = pool.slot0();
uint160 sqrtPriceLowerX96 = TickMath.getSqrtRatioAtTick(
    params.lowerTick
);
uint160 sqrtPriceUpperX96 = TickMath.getSqrtRatioAtTick(
    params.upperTick
);

uint128 liquidity = LiquidityMath.getLiquidityForAmounts(
    sqrtPriceX96,
    sqrtPriceLowerX96,
    sqrtPriceUpperX96,
    params.amount0Desired,
    params.amount1Desired
);
...
```

`LiquidityMath.getLiquidityForAmounts` 是一个新函数，我们将在下一章中讨论它。

下一步是向池中提供流动性并检查池返回的数量：如果它们太低，我们就会回滚。
```solidity
(amount0, amount1) = pool.mint(
    msg.sender,
    params.lowerTick,
    params.upperTick,
    liquidity,
    abi.encode(
        IUniswapV3Pool.CallbackData({
            token0: pool.token0(),
            token1: pool.token1(),
            payer: msg.sender
        })
    )
);

if (amount0 < params.amount0Min || amount1 < params.amount1Min)
    revert SlippageCheckFailed(amount0, amount1);
```

就是这样！
