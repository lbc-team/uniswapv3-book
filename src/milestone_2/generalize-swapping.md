# 广义的交换

这将是本里程碑中最难的一章。在更新代码之前，我们需要了解 Uniswap V3 中交换算法的工作原理。

你可以把交换看作是订单的填充：用户提交一个订单，从池子中购买指定数量的代币。池子将利用可用的流动性，将输入的数量 "转换 "成另一种代币的输出数量。如果当前价格范围内没有足够的流动性，它将尝试在其他价格范围内寻找流动性（使用我们在上一章中实现的函数）。

我们现在将在 `swap` 函数中实现这个逻辑，但是目前只停留在当前价格范围内——我们将在下一个里程碑中实现跨 tick 的交换。

```solidity
function swap(
    address recipient,
    bool zeroForOne,
    uint256 amountSpecified,
    bytes calldata data
) public returns (int256 amount0, int256 amount1) {
    ...
```

在 `swap` 函数中，我们添加了两个新参数：`zeroForOne` 和 `amountSpecified`。`zeroForOne` 是控制交换方向的标志：当 `true` 时，`token0` 被换成 `token1`；当 `false` 时，则相反。例如，如果 `token0` 是 ETH，`token1` 是 USDC，那么将 `zeroForOne` 设置为 `true` 意味着用 ETH 购买 USDC。`amountSpecified` 是用户想要出售的代币数量。

## 填充订单

由于在 Uniswap V3 中，流动性存储在多个价格范围内，因此 Pool 合约需要找到所有 "填充 "用户订单所需的流动性。这是通过在用户选择的方向上迭代初始化后的 tick 来完成的。

在继续之前，我们需要定义两个新的结构体：
```solidity
struct SwapState {
    uint256 amountSpecifiedRemaining;
    uint256 amountCalculated;
    uint160 sqrtPriceX96;
    int24 tick;
}

struct StepState {
    uint160 sqrtPriceStartX96;
    int24 nextTick;
    uint160 sqrtPriceNextX96;
    uint256 amountIn;
    uint256 amountOut;
}
```

`SwapState` 维护当前交换的状态。`amountSpecifiedRemaining` 跟踪池子需要购买的剩余代币数量。当它为零时，交换就完成了。`amountCalculated` 是合约计算出的输出量。`sqrtPriceX96` 和 `tick` 是交换完成后新的当前价格和 tick。

`StepState` 维护当前交换步骤的状态。此结构体跟踪 "订单填充 "的 **一次迭代** 的状态。`sqrtPriceStartX96` 跟踪迭代开始时的价格。`nextTick` 是下一个初始化后的 tick，它将为交换提供流动性，`sqrtPriceNextX96` 是下一个 tick 的价格。`amountIn` 和 `amountOut` 是当前迭代的流动性可以提供的数量。

> 在我们实现跨 tick 交换（即发生在多个价格范围内的交换）之后，迭代的概念将更加清晰。

```solidity
// src/UniswapV3Pool.sol

function swap(...) {
    Slot0 memory slot0_ = slot0;

    SwapState memory state = SwapState({
        amountSpecifiedRemaining: amountSpecified,
        amountCalculated: 0,
        sqrtPriceX96: slot0_.sqrtPriceX96,
        tick: slot0_.tick
    });
    ...
```

在填充订单之前，我们初始化一个 `SwapState` 实例。我们将循环直到 `amountSpecifiedRemaining` 为 0，这将意味着池子有足够的流动性从用户那里购买 `amountSpecified` 个代币。

```solidity
...
while (state.amountSpecifiedRemaining > 0) {
    StepState memory step;

    step.sqrtPriceStartX96 = state.sqrtPriceX96;

    (step.nextTick, ) = tickBitmap.nextInitializedTickWithinOneWord(
        state.tick,
        1,
        zeroForOne
    );

    step.sqrtPriceNextX96 = TickMath.getSqrtRatioAtTick(step.nextTick);
```

在循环中，我们设置一个应该为交换提供流动性的价格范围。范围从 `state.sqrtPriceX96` 到 `step.sqrtPriceNextX96`，后者是下一个初始化后的 tick 的价格（由 `nextInitializedTickWithinOneWord` 返回——我们从前一章知道这个函数）。

```solidity
(state.sqrtPriceX96, step.amountIn, step.amountOut) = SwapMath
    .computeSwapStep(
        state.sqrtPriceX96,
        step.sqrtPriceNextX96,
        liquidity,
        state.amountSpecifiedRemaining
    );
```

接下来，我们计算当前价格范围可以提供的数量，以及交换将导致的新当前价格。

```solidity
    state.amountSpecifiedRemaining -= step.amountIn;
    state.amountCalculated += step.amountOut;
    state.tick = TickMath.getTickAtSqrtRatio(state.sqrtPriceX96);
}
```

循环中的最后一步是更新 SwapState。`step.amountIn` 是价格范围可以从用户那里购买的代币数量；`step.amountOut` 是池子可以出售给用户的另一种代币的相关数量。`state.sqrtPriceX96` 是交换后将设置的当前价格（回想一下，交易会改变当前价格）。

## SwapMath 合约

让我们更仔细地看看 `SwapMath.computeSwapStep`。

```solidity
// src/lib/SwapMath.sol
function computeSwapStep(
    uint160 sqrtPriceCurrentX96,
    uint160 sqrtPriceTargetX96,
    uint128 liquidity,
    uint256 amountRemaining
)
    internal
    pure
    returns (
        uint160 sqrtPriceNextX96,
        uint256 amountIn,
        uint256 amountOut
    )
{
    ...
```

这是交换的核心逻辑。该函数计算一个价格范围内的交换量，并尊重可用的流动性。它将返回：新的当前价格以及输入和输出代币量。即使输入量是由用户提供的，我们仍然要计算它，以了解一次调用 `computeSwapStep` 处理了多少用户指定的输入量。

```solidity
bool zeroForOne = sqrtPriceCurrentX96 >= sqrtPriceTargetX96;

sqrtPriceNextX96 = Math.getNextSqrtPriceFromInput(
    sqrtPriceCurrentX96,
    liquidity,
    amountRemaining,
    zeroForOne
);
```

通过检查价格，我们可以确定交换的方向。知道方向后，我们可以计算交换 `amountRemaining` 数量的代币之后的价格。我们将在下面回到这个函数。

在找到新价格后，我们可以使用我们已经拥有的函数来计算交换的输入和输出量（与我们在 `mint` 函数中用于从流动性计算代币量的函数相同）：
```solidity
amountIn = Math.calcAmount0Delta(
    sqrtPriceCurrentX96,
    sqrtPriceNextX96,
    liquidity
);
amountOut = Math.calcAmount1Delta(
    sqrtPriceCurrentX96,
    sqrtPriceNextX96,
    liquidity
);
```

如果方向相反，则交换数量：
```solidity
if (!zeroForOne) {
    (amountIn, amountOut) = (amountOut, amountIn);
}
```

`computeSwapStep` 就是这样！

## 通过交换量查找价格

现在让我们看看 `Math.getNextSqrtPriceFromInput`——该函数根据另一个 $\sqrt{P}$、流动性和输入量来计算 $\sqrt{P}$。它告诉你在交换指定数量的代币输入量后，给定当前价格和流动性，价格会是多少。

好消息是，我们已经知道了公式：回想一下我们如何在 Python 中计算 `price_next`：
```python
# When amount_in is token0
price_next = int((liq * q96 * sqrtp_cur) // (liq * q96 + amount_in * sqrtp_cur))
# When amount_in is token1
price_next = sqrtp_cur + (amount_in * q96) // liq
```

我们将在 Solidity 中实现这一点：
```solidity
// src/lib/Math.sol
function getNextSqrtPriceFromInput(
    uint160 sqrtPriceX96,
    uint128 liquidity,
    uint256 amountIn,
    bool zeroForOne
) internal pure returns (uint160 sqrtPriceNextX96) {
    sqrtPriceNextX96 = zeroForOne
        ? getNextSqrtPriceFromAmount0RoundingUp(
            sqrtPriceX96,
            liquidity,
            amountIn
        )
        : getNextSqrtPriceFromAmount1RoundingDown(
            sqrtPriceX96,
            liquidity,
            amountIn
        );
}
```

该函数处理两个方向的交换。由于计算方式不同，我们将它们在单独的函数中实现。

```solidity
function getNextSqrtPriceFromAmount0RoundingUp(
    uint160 sqrtPriceX96,
    uint128 liquidity,
    uint256 amountIn
) internal pure returns (uint160) {
    uint256 numerator = uint256(liquidity) << FixedPoint96.RESOLUTION;
    uint256 product = amountIn * sqrtPriceX96;

    if (product / amountIn == sqrtPriceX96) {
        uint256 denominator = numerator + product;
        if (denominator >= numerator) {
            return
                uint160(
                    mulDivRoundingUp(numerator, sqrtPriceX96, denominator)
                );
        }
    }

    return
        uint160(
            divRoundingUp(numerator, (numerator / sqrtPriceX96) + amountIn)
        );
}
```
在这个函数中，我们实现了两个公式。在第一个 `return` 中，它实现了我们在 Python 中实现的相同公式。这是最精确的公式，但当 `amountIn` 乘以 `sqrtPriceX96` 时，它可能会溢出。该公式是（我们在 "输出金额计算 "中讨论过）：
$$\sqrt{P_{target}} = \frac{\sqrt{P}L}{\Delta x \sqrt{P} + L}$$

当它溢出时，我们使用替代公式，该公式不太精确：
$$\sqrt{P_{target}} = \frac{L}{\Delta x + \frac{L}{\sqrt{P}}}$$

这仅仅是前一个公式，分子和分母都除以 $\sqrt{P}$ 以消除分子中的乘法。

另一个函数的数学运算更简单：
```solidity
function getNextSqrtPriceFromAmount1RoundingDown(
    uint160 sqrtPriceX96,
    uint128 liquidity,
    uint256 amountIn
) internal pure returns (uint160) {
    return
        sqrtPriceX96 +
        uint160((amountIn << FixedPoint96.RESOLUTION) / liquidity);
}
```

## 完成交换

现在，让我们回到 `swap` 函数并完成它。

至此，我们已经循环遍历了下一个初始化后的 tick，填充了用户指定的 `amountSpecified`，计算了输入和数量，并找到了新的价格和 tick。由于在本里程碑中，我们只实现一个价格范围内的交换，因此这已经足够了。我们现在需要更新合约的状态，将代币发送给用户，并换取代币。

```solidity
if (state.tick != slot0_.tick) {
    (slot0.sqrtPriceX96, slot0.tick) = (state.sqrtPriceX96, state.tick);
}
```

首先，我们设置一个新的价格和 tick。由于此操作会写入合约的存储，因此我们只想在新 tick 不同的情况下才执行此操作，以优化 gas 消耗。

```solidity
(amount0, amount1) = zeroForOne
    ? (
        int256(amountSpecified - state.amountSpecifiedRemaining),
        -int256(state.amountCalculated)
    )
    : (
        -int256(state.amountCalculated),
        int256(amountSpecified - state.amountSpecifiedRemaining)
    );
```

接下来，我们根据交换方向和交换循环期间计算的数量来计算交换量。

```solidity
if (zeroForOne) {
    IERC20(token1).transfer(recipient, uint256(-amount1));

    uint256 balance0Before = balance0();
    IUniswapV3SwapCallback(msg.sender).uniswapV3SwapCallback(
        amount0,
        amount1,
        data
    );
    if (balance0Before + uint256(amount0) > balance0())
        revert InsufficientInputAmount();
} else {
    IERC20(token0).transfer(recipient, uint256(-amount0));

    uint256 balance1Before = balance1();
    IUniswapV3SwapCallback(msg.sender).uniswapV3SwapCallback(
        amount0,
        amount1,
        data
    );
    if (balance1Before + uint256(amount1) > balance1())
        revert InsufficientInputAmount();
}
```

接下来，我们根据交换方向与用户交换代币。这一部分与我们在里程碑 2 中的内容相同，只是添加了对另一个交换方向的处理。

就这样！交换完成！

## 测试

测试不会发生重大变化，我们只需要将 `amountSpecified` 和 `zeroForOne` 传递给 `swap` 函数即可。输出量会发生很小的变化，因为它现在是在 Solidity 中计算的。

我们现在可以测试相反方向的交换！我将把这作为家庭作业留给你（只需确保选择一个小的输入量，以便我们单个价格范围可以处理整个交换）。如果这感觉很困难，请随时查看[我的测试](https://github.com/Jeiwan/uniswapv3-code/blob/milestone_2/test/UniswapV3Pool.t.sol)！
