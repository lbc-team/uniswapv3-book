# 跨 Tick 交易

跨 tick 交易可能是 Uniswap V3 最先进的功能。幸运的是，我们已经实现了几乎所有我们需要实现跨 tick 交易的功能。在实现代码之前，让我们先看看跨 tick 交易是如何工作的。

## 跨 Tick 交易如何工作

一个常见的 Uniswap V3 池是一个具有许多重叠（和突出）价格范围的池。每个池跟踪当前的 $\sqrt{P}$ 和 tick。当用户交换代币时，他们会根据交换方向，将当前价格和 tick 向左或向右移动。这些移动是由交换期间添加到池中和从池中移除的代币引起的。

池也跟踪 $L$（我们代码中的 `liquidity` 变量），它是**包含当前价格的所有价格范围提供的总流动性**。可以预见的是，在大的价格变动期间，当前价格会移动到价格范围之外。当这种情况发生时，这些价格范围会变为不活跃，并且它们的流动性会从 $L$ 中减去。另一方面，当当前价格进入一个价格范围时，$L$ 会增加，并且该价格范围会激活。

让我们分析一下这个图示：

![价格范围的动态](https://img.learnblockchain.cn/how_to_defi/uniswapv3/src/milestone_3/images/price_range_dynamics.png)

此图中有三个价格范围。最上面的一个（top one）是当前正在使用的，它包含当前价格。此价格范围的流动性设置为 Pool 合约的 `liquidity` 状态变量。

如果我们从最上面的价格范围购买所有 ETH，价格将会上涨，并且我们将移动到右边的价格范围，此时此价格范围只包含 ETH，不包含 USDC。如果此价格范围有足够的流动性来满足我们的需求，我们可能会在此价格范围停止。在这种情况下，`liquidity` 变量将只包含此价格范围提供的流动性。如果我们继续购买 ETH 并耗尽最右边的价格范围，我们将需要另一个位于此价格范围右侧的价格范围。如果没有更多价格范围，我们将不得不停止，并且我们的交易将只会被部分满足。

如果我们从最上面的价格范围购买所有 USDC（并出售 ETH），价格将会下降，并且我们将移动到左边的价格范围——此时它只包含 USDC。如果我们耗尽了它，我们将需要另一个位于其左侧的价格范围。

当前价格在交易期间移动。它从一个价格范围移动到另一个价格范围，但它必须始终保持在一个价格范围内——否则，交易是不可能的。

当然，价格范围可以重叠，因此，在实践中，价格范围之间的过渡是无缝的。并且不可能跳过一个缺口——交易会被部分完成。同样值得注意的是，在价格范围重叠的区域，价格移动得较慢。这是因为在这些区域供应量较高，需求的影响较小（回顾一下介绍部分，低供应量下的高需求会提高价格）。

我们当前的实现不支持这种流动性：我们只允许在一个活跃的价格范围内进行交易。这就是我们现在要改进的地方。

## 更新 `computeSwapStep` 函数

在 `swap` 函数中，我们正在迭代已初始化的 tick（即具有流动性的 tick）来填充用户请求的数量。在每次迭代中，我们：

1. 使用 `tickBitmap.nextInitializedTickWithinOneWord` 找到下一个已初始化的 tick；
2. 在当前价格和下一个已初始化的 tick 之间的范围内进行交易（使用 `SwapMath.computeSwapStep`）；
3. 始终期望当前的流动性足以满足交易（即，交易后的价格位于当前价格和下一个已初始化的 tick 之间）。

但是，如果第三步不成立会发生什么？我们在测试中涵盖了这种情况：
```solidity
// test/UniswapV3Pool.t.sol
function testSwapBuyEthNotEnoughLiquidity() public {
    ...

    uint256 swapAmount = 5300 ether;

    ...

    vm.expectRevert(stdError.arithmeticError);
    pool.swap(address(this), false, swapAmount, extra);
}
```

当池试图发送给我们比它拥有的更多的 ether 时，会发生“算术上溢/下溢”。发生此错误是因为，在我们当前的实现中，我们始终期望有足够的流动性来满足任何交易：

```solidity
// src/lib/SwapMath.sol
function computeSwapStep(...) {
    ...

    sqrtPriceNextX96 = Math.getNextSqrtPriceFromInput(
        sqrtPriceCurrentX96,
        liquidity,
        amountRemaining,
        zeroForOne
    );

    amountIn = ...
    amountOut = ...
}
```

为了改进这一点，我们需要考虑几种情况：
1. 当前 tick 和下一个 tick 之间的范围有足够的流动性来填充 `amountRemaining` 时；
2. 该范围不能填充整个 `amountRemaining` 时。

在第一种情况下，交易完全在范围内完成——这是我们已经实现的场景。在第二种情况下，我们将消耗该范围提供的所有流动性，并且**将移动到下一个范围**（如果存在）。考虑到这一点，让我们重新构建 `computeSwapStep`：
```solidity
// src/lib/SwapMath.sol
function computeSwapStep(...) {
    ...
    amountIn = zeroForOne
        ? Math.calcAmount0Delta(
            sqrtPriceCurrentX96,
            sqrtPriceTargetX96,
            liquidity
        )
        : Math.calcAmount1Delta(
            sqrtPriceCurrentX96,
            sqrtPriceTargetX96,
            liquidity
        );

    if (amountRemaining >= amountIn) sqrtPriceNextX96 = sqrtPriceTargetX96;
    else
        sqrtPriceNextX96 = Math.getNextSqrtPriceFromInput(
            sqrtPriceCurrentX96,
            liquidity,
            amountRemaining,
            zeroForOne
        );

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
}
```
首先，我们计算 `amountIn`——当前范围可以满足的输入量。如果它小于 `amountRemaining`，我们说当前价格范围无法满足整个交易，因此下一个 $\sqrt{P}$ 是价格范围的上限/下限 $\sqrt{P}$（换句话说，我们使用整个价格范围的流动性）。如果 `amountIn` 大于 `amountRemaining`，我们计算 `sqrtPriceNextX96`——它将是当前价格范围内的价格。

最后，在确定了下一个价格之后，我们重新计算 `amountIn` 并在较短的价格范围内计算 `amountOut`（我们不消耗整个流动性）。

我希望这说得通！

## 更新 `swap` 函数

现在，在 `swap` 函数中，我们需要处理我们在上一部分中介绍的情况：当交易价格达到价格范围的边界时。当这种情况发生时，我们想要停用我们离开的价格范围并激活下一个价格范围。我们还想开始循环的另一次迭代，并尝试找到另一个具有流动性的 tick。

在更新循环之前，让我们将 `tickBitmap.nextInitializedTickWithinOneWord()` 调用返回的第二个值保存到 `step.initialized` 中：
```solidity
(step.nextTick, step.initialized) = tickBitmap.nextInitializedTickWithinOneWord(
    state.tick,
    1,
    zeroForOne
);
```

（在之前的里程碑中，我们只存储了 `step.nextTick`。）

知道下一个 tick 是否被初始化将帮助我们在 ticks 位图中的当前 word 中没有已初始化的 tick 时节省一些 gas。

现在，这是我们需要添加到循环末尾的内容：
```solidity
if (state.sqrtPriceX96 == step.sqrtPriceNextX96) {
    if (step.initialized) {
        int128 liquidityDelta = ticks.cross(step.nextTick);

        if (zeroForOne) liquidityDelta = -liquidityDelta;

        state.liquidity = LiquidityMath.addLiquidity(
            state.liquidity,
            liquidityDelta
        );

        if (state.liquidity == 0) revert NotEnoughLiquidity();
    }

    state.tick = zeroForOne ? step.nextTick - 1 : step.nextTick;
} else {
    state.tick = TickMath.getTickAtSqrtRatio(state.sqrtPriceX96);
}
```

第二个分支是我们之前拥有的——它处理当前价格保持在范围内的这种情况。因此，让我们关注第一个分支。

在这里，我们正在更新当前流动性，但仅当下一个 tick 已初始化时（如果未初始化，我们跳过向流动性添加 0 以节省 gas）。

`state.sqrtPriceX96` 是新的当前价格，即将在当前交易之后设置的价格；`step.sqrtPriceNextX96` 是下一个已初始化 tick 的价格。如果这些相等，我们已经达到了价格范围边界。如上所述，当这种情况发生时，我们想要更新 $L$（添加或移除流动性），并使用边界 tick 作为当前 tick 继续进行交易。

按照惯例，跨越一个 tick 意味着从左到右跨越它。因此，跨越较低的 tick 总是增加流动性，而跨越较高的 tick 总是移除流动性。但是，当 `zeroForOne` 为 true 时，我们否定符号：当价格下降（代币 $x$ 正在出售）时，较高的 tick 增加流动性，而较低的 tick 移除流动性。

当更新 `state.tick` 时，如果价格下降（`zeroForOne` 为 true），我们需要减去 1 以退出价格范围。当向上移动（`zeroForOne` 为 false）时，当前 tick 始终在 `TickBitmap.nextInitializedTickWithinOneWord` 中排除。

我们需要做的另一个小的，但非常重要的更改是在跨越 tick 时更新 $L$。我们在循环之后执行此操作：
```solidity
if (liquidity_ != state.liquidity) liquidity = state.liquidity;
```

在循环中，当进入/离开价格范围时，我们会多次更新 `state.liquidity`。在交易之后，我们需要更新全局 $L$，以使其反映新当前价格可用的流动性。此外，我们仅在完成交易时才更新全局变量的原因是 gas 消耗优化，因为写入合约的存储空间是一项昂贵的操作。

## 流动性跟踪和 Ticks 跨越

现在让我们看一下更新后的 `Tick` 库。

第一个更改是在 `Tick.Info` 结构中：我们现在有两个变量来跟踪 tick 流动性：
```solidity
struct Info {
    bool initialized;
    // total liquidity at tick
    uint128 liquidityGross;
    // amount of liquidity added or subtracted when tick is crossed
    int128 liquidityNet;
}
```

`liquidityGross` 跟踪一个 tick 的绝对流动性数量。需要它来查找一个 tick 是否被翻转。另一方面，`liquidityNet` 是一个有符号的整数——它跟踪跨越一个 tick 时添加（在较低的 tick 的情况下）或移除（在较高的 tick 的情况下）的流动性数量。

`liquidityNet` 在 `update` 函数中设置：
```solidity
function update(
    mapping(int24 => Tick.Info) storage self,
    int24 tick,
    int128 liquidityDelta,
    bool upper
) internal returns (bool flipped) {
    ...

    tickInfo.liquidityNet = upper
        ? int128(int256(tickInfo.liquidityNet) - liquidityDelta)
        : int128(int256(tickInfo.liquidityNet) + liquidityDelta);
}
```

我们在上面看到的 `cross` 函数只是返回 `liquidityNet`（在我们稍后的里程碑中引入新功能后，它会变得更加复杂）：
```solidity
function cross(mapping(int24 => Tick.Info) storage self, int24 tick)
    internal
    view
    returns (int128 liquidityDelta)
{
    Tick.Info storage info = self[tick];
    liquidityDelta = info.liquidityNet;
}
```

## 测试

让我们回顾不同的流动性设置并对其进行测试，以确保我们的池实现可以正确处理它们。

### 一个价格范围

![在价格范围内交易](https://img.learnblockchain.cn/how_to_defi/uniswapv3/src/milestone_3/images/swap_within_price_range.png)

这是我们之前的情况。在更新代码后，我们需要确保旧功能保持正常工作。

> 为了简洁起见，我将仅显示测试的最重要部分。你可以在[代码仓库](https://github.com/Jeiwan/uniswapv3-code/blob/milestone_3/test/UniswapV3Pool.Swaps.t.sol)中找到完整的测试。

- 当购买 ETH 时：
    ```solidity
    function testBuyETHOnePriceRange() public {
        LiquidityRange[] memory liquidity = new LiquidityRange[](1);
        liquidity[0] = liquidityRange(4545, 5500, 1 ether, 5000 ether, 5000);

        ...

        (int256 expectedAmount0Delta, int256 expectedAmount1Delta) = (
            -0.008396874645169943 ether,
            42 ether
        );

        assertSwapState(
            ExpectedStateAfterSwap({
                ...
                sqrtPriceX96: 5604415652688968742392013927525, // 5003.8180249710795
                tick: 85183,
                currentLiquidity: liquidity[0].amount
            })
        );
    }
    ```
- 当购买 USDC 时：
    ```solidity
    function testBuyUSDCOnePriceRange() public {
        LiquidityRange[] memory liquidity = new LiquidityRange[](1);
        liquidity[0] = liquidityRange(4545, 5500, 1 ether, 5000 ether, 5000);

        ...

        (int256 expectedAmount0Delta, int256 expectedAmount1Delta) = (
            0.01337 ether,
            -66.807123823853842027 ether
        );

        assertSwapState(
            ExpectedStateAfterSwap({
                ...
                sqrtPriceX96: 5598737223630966236662554421688, // 4993.683362269102
                tick: 85163,
                currentLiquidity: liquidity[0].amount
            })
        );
    }
    ```

在这两种情况下，我们购买少量 ETH 或 USDC——它需要足够小，才能使价格不会超出我们创建的唯一价格范围。完成交易后的关键值：
1. `sqrtPriceX96` 略高于或低于初始价格，并保持在价格范围内；
2. `currentLiquidity` 保持不变。

### 多个相同且重叠的价格范围

![在重叠范围内交易](https://img.learnblockchain.cn/how_to_defi/uniswapv3/src/milestone_3/images/swap_within_overlapping_price_ranges.png)

- 当购买 ETH 时：
    ```solidity
    function testBuyETHTwoEqualPriceRanges() public {
        LiquidityRange memory range = liquidityRange(
            4545,
            5500,
            1 ether,
            5000 ether,
            5000
        );
        LiquidityRange[] memory liquidity = new LiquidityRange[](2);
        liquidity[0] = range;
        liquidity[1] = range;

        ...

        (int256 expectedAmount0Delta, int256 expectedAmount1Delta) = (
            -0.008398516982770993 ether,
            42 ether
        );

        assertSwapState(
            ExpectedStateAfterSwap({
                ...
                sqrtPriceX96: 5603319704133145322707074461607, // 5001.861214026131
                tick: 85179,
                currentLiquidity: liquidity[0].amount + liquidity[1].amount
            })
        );
    }
    ```

- 当购买 USDC 时：
    ```solidity
    function testBuyUSDCTwoEqualPriceRanges() public {
        LiquidityRange memory range = liquidityRange(
            4545,
            5500,
            1 ether,
            5000 ether,
            5000
        );
        LiquidityRange[] memory liquidity = new LiquidityRange[](2);
        liquidity[0] = range;
        liquidity[1] = range;
        
        ...

        (int256 expectedAmount0Delta, int256 expectedAmount1Delta) = (
            0.01337 ether,
            -66.827918929906650442 ether
        );

        assertSwapState(
            ExpectedStateAfterSwap({
                ...
                sqrtPriceX96: 5600479946976371527693873969480, // 4996.792621611429
                tick: 85169,
                currentLiquidity: liquidity[0].amount + liquidity[1].amount
            })
        );
    }
    ```

这种情况与前一种情况类似，但这次我们创建了两个相同的价格范围。由于这些是完全重叠的价格范围，因此它们实际上就像一个具有更高流动性数量的价格范围。因此，价格变化比前一种情况慢。此外，由于更深的流动性，我们获得了稍微更多的代币。

### 连续的价格范围

![跨越连续价格范围的交易](https://img.learnblockchain.cn/how_to_defi/uniswapv3/src/milestone_3/images/swap_consecutive_price_ranges.png)

- 当购买 ETH 时：
    ```solidity
    function testBuyETHConsecutivePriceRanges() public {
        LiquidityRange[] memory liquidity = new LiquidityRange[](2);
        liquidity[0] = liquidityRange(4545, 5500, 1 ether, 5000 ether, 5000);
        liquidity[1] = liquidityRange(5500, 6250, 1 ether, 5000 ether, 5000);

        ...

        (int256 expectedAmount0Delta, int256 expectedAmount1Delta) = (
            -1.820694594787485635 ether,
            10000 ether
        );

        assertSwapState(
            ExpectedStateAfterSwap({
                ...
                sqrtPriceX96: 6190476002219365604851182401841, // 6105.045728033458
                tick: 87173,
                currentLiquidity: liquidity[1].amount
            })
        );
    }
    ```
- 当购买 USDC 时：
    ```solidity
    function testBuyUSDCConsecutivePriceRanges() public {
        LiquidityRange[] memory liquidity = new LiquidityRange[](2);
        liquidity[0] = liquidityRange(4545, 5500, 1 ether, 5000 ether, 5000);
        liquidity[1] = liquidityRange(4000, 4545, 1 ether, 5000 ether, 5000);
        
        ...

        (int256 expectedAmount0Delta, int256 expectedAmount1Delta) = (
            2 ether,
            -9103.264925902176327184 ether
        );

        assertSwapState(
            ExpectedStateAfterSwap({
                ...
                sqrtPriceX96: 5069962753257045266417033265661, // 4094.9666586581643
                tick: 83179,
                currentLiquidity: liquidity[1].amount
            })
        );
    }
    ```

在这些情况下，我们进行大的交易，导致价格超出价格范围。结果，第二个价格范围被激活，并提供足够的流动性来满足交易。在两种情况下，我们可以看到价格落在当前价格范围之外，并且价格范围被停用（当前流动性等于第二个价格范围的流动性）。

### 部分重叠的价格范围

![跨越部分重叠价格范围的交易](https://img.learnblockchain.cn/how_to_defi/uniswapv3/src/milestone_3/images/swap_partially_overlapping_price_ranges.png)

- 当购买 ETH 时：
    ```solidity
    function testBuyETHPartiallyOverlappingPriceRanges() public {
        LiquidityRange[] memory liquidity = new LiquidityRange[](2);
        liquidity[0] = liquidityRange(4545, 5500, 1 ether, 5000 ether, 5000);
        liquidity[1] = liquidityRange(5001, 6250, 1 ether, 5000 ether, 5000);
        
        ...

        (int256 expectedAmount0Delta, int256 expectedAmount1Delta) = (
            -1.864220641170389178 ether,
            10000 ether
        );

        assertSwapState(
            ExpectedStateAfterSwap({
                ...
                sqrtPriceX96: 6165345094827913637987008642386, // 6055.578153852725
                tick: 87091,
                currentLiquidity: liquidity[1].amount
            })
        );
    }
    ```

- 当购买 USDC 时：
    ```solidity
    function testBuyUSDCPartiallyOverlappingPriceRanges() public {
        LiquidityRange[] memory liquidity = new LiquidityRange[](2);
        liquidity[0] = liquidityRange(4545, 5500, 1 ether, 5000 ether, 5000);
        liquidity[1] = liquidityRange(4000, 4999, 1 ether, 5000 ether, 5000);
        
        ...

        (int256 expectedAmount0Delta, int256 expectedAmount1Delta) = (
            2 ether,
            -9321.077831210790476918 ether
        );

        assertSwapState(
            ExpectedStateAfterSwap({
                ...
                sqrtPriceX96: 5090915820491052794734777344590, // 4128.883835866256
                tick: 83261,
                currentLiquidity: liquidity[1].amount
            })
        );
    }
    ```

这是前一种情况的变体，但这次价格范围是部分重叠的。在价格范围重叠的区域中，有更深的流动性，这使得价格移动更慢。这类似于在重叠范围中提供更多的流动性。

另请注意，在两次交易中，我们都比“连续价格范围”情况下获得了更多的代币——这再次是由于重叠范围中更深的流动性所致。