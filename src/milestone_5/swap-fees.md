# 兑换费用

正如我在引言中提到的，兑换费用是 Uniswap 的一个核心机制。流动性提供者需要为其提供的流动性获得报酬，否则他们会将流动性用于其他地方。为了激励他们，交易在每次兑换时支付少量费用。这些费用然后按比例（与其在总流动性池中的份额成比例）分配给所有流动性提供者。

为了更好地理解费用收集和分配的机制，让我们看看它们是如何运作的。

## 如何收取兑换费用

![流动性范围和费用](images/liquidity_ranges_fees.png)

兑换费用仅在价格范围被激活（用于交易）时才会被收取。因此，我们需要跟踪价格范围边界被跨越的时刻。这就是价格范围被激活的时刻，也是我们想要开始为其收取费用的时刻：
1. 当价格上涨并且从左到右跨越一个 tick 时；
1. 当价格下跌并且从右到左跨越一个 tick 时。

这是价格范围被解除激活的时刻：
1. 当价格上涨并且从右到左跨越一个 tick 时；
1. 当价格下跌并且从左到右跨越一个 tick 时。

![流动性范围激活/解除激活](images/liquidity_range_engaged.png)

除了知道价格范围何时被激活/解除激活之外，我们还希望跟踪每个价格范围累积了多少费用。

为了简化费用核算，Uniswap V3 跟踪**每 1 个单位的流动性产生的全局费用**。然后根据全局费用计算价格范围费用：从全局费用中减去在价格范围之外累积的费用。当跨越一个 tick 时（当兑换移动价格时，tick 会被跨越；费用在兑换期间收取），会跟踪在价格范围之外累积的费用。通过这种方法，我们不需要在每次兑换时更新每个仓位累积的费用——这使我们能够节省大量 gas 并使与池的交互更便宜。

让我们回顾一下，以便在继续之前有一个清晰的了解：
1. 费用由兑换代币的用户支付。一小部分从输入代币中扣除并累积在池的余额中。
1. 每个池都有 `feeGrowthGlobal0X128` 和 `feeGrowthGlobal1X128` 状态变量，用于跟踪每个流动性单位累积的总费用（即费用金额除以池的流动性）。
1. 请注意，此时不会更新实际的仓位，以优化 gas 的使用。
1. Ticks 记录在它们之外累积的费用。当添加新的仓位并激活一个 tick 时（向之前为空的 tick 添加流动性），该 tick 会记录在其之外累积了多少费用（按照惯例，我们假设所有费用都累积在 **tick 的下方**）。
1. 每当激活一个 tick 时，在该 tick 之外累积的费用都会更新为自上次跨越以来在该 tick 之外累积的全局费用与在该 tick 之外累积的费用之间的差额。
1. 拥有知道在其之外累积了多少费用的 ticks 将使我们能够计算在一个仓位内累积了多少费用（仓位是两个 ticks 之间的范围）。
1. 知道在一个仓位内累积了多少费用将使我们能够计算流动性提供者有资格获得的费用份额。如果一个仓位没有参与兑换，那么它内部将累积零费用，并且将流动性提供到该范围的流动性提供者将不会从中获利。

现在，让我们看看如何计算一个仓位累积的费用（步骤 6）。

## 计算仓位累计费用

要计算一个仓位累积的总费用，我们需要考虑两种情况：当当前价格在该仓位内时，以及当当前价格在该仓位外时。在这两种情况下，我们都会从全局收取的费用中减去在该仓位下限和上限的 tick 之外收取的费用。但是，我们会根据当前价格以不同的方式计算这些费用。

当当前价格在该仓位内时，我们减去到目前为止在 tick 之外收取的费用：

![在价格范围内外应计的费用](images/fees_inside_and_outside_price_range.png)

当当前价格在该仓位之外时，我们需要在从全局收取的费用中减去它们之前，更新上限或下限 tick 收取的费用。我们仅针对计算更新它们，而不在 ticks 中覆盖它们，因为 ticks 没有被跨越。

这是我们更新在 tick 之外收取的费用的方式：

$$f_{o}(i) = f_{g} - f_{o}(i)$$

在 tick 之外收取的费用 ($f_{o}(i)$) 是全局收取的费用 ($f_{g}$) 与上次跨越时在该 tick 之外收取的费用之间的差额。当跨越一个 tick 时，我们有点重置计数器。

要计算在仓位内收取的费用：

$$f_{r} = f_{g} - f_{b}(i_{l}) - f_{a}(i_{u})$$

我们从所有价格范围收取的全局费用 ($f_{g}$) 中减去在其下限 tick 之下收取的费用 ($f_{b}(i_{l})$) 和在其上限 tick 之上收取的费用 ($f_{a}(i_{u})$)。这就是我们在上面的插图中看到的。

现在，当当前价格高于下限 tick 时（即，该仓位已激活），我们不需要更新在下限 tick 之下累积的费用，可以直接从下限 tick 中获取它们。当当前价格低于上限 tick 时，对于在上限 tick 之外收取的费用也是如此。在其他两种情况下，我们需要考虑更新的费用：
1. 当获取在下限 tick 之下收取的费用，并且当前价格也低于该 tick 时（下限 tick 最近没有被跨越）。
1. 当获取在上限 tick 之上收取的费用，并且当前价格也高于该 tick 时（上限 tick 最近没有被跨越）。

我希望这不会太令人困惑。幸运的是，我们现在知道开始编码所需的一切！

## 应计兑换费用

为了简单起见，我们将逐步向我们的代码库添加费用。我们将从应计兑换费用开始。

### 添加所需的状态变量
我们需要做的第一件事是将费用金额参数添加到 Pool——每个池都将在部署期间配置一个固定的、不可变的费用。在上一章中，我们添加了 Factory 合约，该合约统一并简化了池的部署。所需池参数之一是 tick 间隔。现在，我们将用费用金额替换它，并且我们将费用金额与 tick 间隔联系起来：费用金额越大，tick 间隔越大。这是为了使低波动性池（稳定币池）具有较低的费用。

让我们更新 Factory：
```solidity
// src/UniswapV3Factory.sol
contract UniswapV3Factory is IUniswapV3PoolDeployer {
    ...
    mapping(uint24 => uint24) public fees; // `tickSpacings` 被 `fees` 替换

    constructor() {
        fees[500] = 10;
        fees[3000] = 60;
    }

    function createPool(
        address tokenX,
        address tokenY,
        uint24 fee
    ) public returns (address pool) {
        ...
        parameters = PoolParameters({
            factory: address(this),
            token0: tokenX,
            token1: tokenY,
            tickSpacing: fees[fee],
            fee: fee
        });
        ...
    }
}
```

费用金额是基点的百分之一百。也就是说，1 个费用单位是 0.0001%，500 是 0.05%，3000 是 0.3%。

下一步是开始在 Pool 中累积费用。为此，我们将添加两个全局费用累加器变量：
```solidity
// src/UniswapV3Pool.sol
contract UniswapV3Pool is IUniswapV3Pool {
    ...
    uint24 public immutable fee;
    uint256 public feeGrowthGlobal0X128;
    uint256 public feeGrowthGlobal1X128;
}
```

索引为 0 的那个跟踪在 `token0` 中累积的费用，索引为 1 的那个跟踪在 `token1` 中累积的费用。

### 收取费用

现在我们需要更新 `SwapMath.computeSwapStep`——这是我们计算兑换金额的地方，也是我们计算并扣除兑换费用的地方。在该函数中，我们将所有出现的 `amountRemaining` 替换为 `amountRemainingLessFee`：
```solidity
uint256 amountRemainingLessFee = PRBMath.mulDiv(
    amountRemaining,
    1e6 - fee,
    1e6
);
```

因此，我们从输入代币金额中减去费用，并从较小的输入金额计算输出金额。

该函数现在还返回在该步骤中收取的费用金额——它的计算方式不同，具体取决于是否达到了范围的上限：
```solidity
bool max = sqrtPriceNextX96 == sqrtPriceTargetX96;
if (!max) {
    feeAmount = amountRemaining - amountIn;
} else {
    feeAmount = Math.mulDivRoundingUp(amountIn, fee, 1e6 - fee);
}
```
当未达到时，当前价格范围有足够的流动性来完成兑换，因此我们只需返回我们需要完成的数量与实际完成数量之间的差额。请注意，`amountRemainingLessFee` 不涉及此处，因为实际的最终金额是在 `amountIn` 中计算的（它是根据可用流动性计算的）。

当达到目标价格时，我们不能从整个 `amountRemaining` 中扣除费用，因为当前价格范围没有足够的流动性来完成兑换。因此，费用金额是从当前价格范围已完成的数量 (`amountIn`) 中扣除的。

在 `SwapMath.computeSwapStep` 返回之后，我们需要更新兑换累积的费用。请注意，只有一个变量来跟踪它们，因为在开始兑换时，我们已经知道输入代币（在兑换期间，费用是在 `token0` 或 `token1` 中收取的，而不是两者）：
```solidity
SwapState memory state = SwapState({
    ...
    feeGrowthGlobalX128: zeroForOne
        ? feeGrowthGlobal0X128
        : feeGrowthGlobal1X128
});

(...) = SwapMath.computeSwapStep(...);

state.feeGrowthGlobalX128 += PRBMath.mulDiv(
    step.feeAmount,
    FixedPoint128.Q128,
    state.liquidity
);
```

这就是我们根据流动性调整应计费用的地方，以便以后以公平的方式在流动性提供者之间分配费用。

### 更新 Ticks 中的费用跟踪器

接下来，我们需要更新一个 tick 中的费用跟踪器，如果在兑换期间它被跨越（跨越一个 tick 意味着我们正在进入一个新的价格范围）：
```solidity
if (state.sqrtPriceX96 == step.sqrtPriceNextX96) {
    int128 liquidityDelta = ticks.cross(
        step.nextTick,
        (
            zeroForOne
                ? state.feeGrowthGlobalX128
                : feeGrowthGlobal0X128
        ),
        (
            zeroForOne
                ? feeGrowthGlobal1X128
                : state.feeGrowthGlobalX128
        )
    );
    ...
}
```

由于我们尚未更新此时的 `feeGrowthGlobal0X128/feeGrowthGlobal1X128` 状态变量，因此我们根据兑换方向将 `state.feeGrowthGlobalX128` 作为任一费用参数传递。`cross` 函数按照我们上面讨论的方式更新费用跟踪器：
```solidity
// src/lib/Tick.sol
function cross(
    mapping(int24 => Tick.Info) storage self,
    int24 tick,
    uint256 feeGrowthGlobal0X128,
    uint256 feeGrowthGlobal1X128
) internal returns (int128 liquidityDelta) {
    Tick.Info storage info = self[tick];
    info.feeGrowthOutside0X128 =
        feeGrowthGlobal0X128 -
        info.feeGrowthOutside0X128;
    info.feeGrowthOutside1X128 =
        feeGrowthGlobal1X128 -
        info.feeGrowthOutside1X128;
    liquidityDelta = info.liquidityNet;
}
```

> 我们尚未添加 `feeGrowthOutside0X128/feeGrowthOutside1X128` 变量的初始化——我们将在稍后的步骤中执行此操作。

### 更新全局费用跟踪器

最后，在完成兑换后，我们可以更新全局费用跟踪器：
```solidity
if (zeroForOne) {
    feeGrowthGlobal0X128 = state.feeGrowthGlobalX128;
} else {
    feeGrowthGlobal1X128 = state.feeGrowthGlobalX128;
}
```
同样，在兑换期间，只有其中一个会被更新，因为费用是从输入代币中扣除的，具体取决于兑换方向，输入代币可以是 `token0` 或 `token1`。

这就是兑换的全部内容！现在让我们看看添加流动性时费用会发生什么。

## 仓位管理中的费用跟踪

当添加或移除流动性时（我们尚未实现后者），我们还需要初始化或更新费用。需要在 ticks 中跟踪费用（在 ticks 之外累积的费用——我们刚刚添加的 `feeGrowthOutside` 变量）和仓位中跟踪费用（在仓位内部累积的费用）。在仓位的情况下，我们还需要跟踪和更新作为费用收取的代币数量——或者换句话说，我们将每个流动性的费用转换为代币数量。后者是必需的，以便当流动性提供者移除流动性时，他们会获得作为兑换费用收取的额外代币。

让我们再次逐步进行。

### 初始化 Ticks 中的费用跟踪器

在 `Tick.update` 函数中，每当初始化一个 tick 时（将流动性添加到先前为空的 tick），我们都会初始化其费用跟踪器。但是，我们仅在 tick 低于当前价格时才这样做，即当它位于当前价格范围之内时：

```solidity
// src/lib/Tick.sol
function update(
    mapping(int24 => Tick.Info) storage self,
    int24 tick,
    int24 currentTick,
    int128 liquidityDelta,
    uint256 feeGrowthGlobal0X128,
    uint256 feeGrowthGlobal1X128,
    bool upper
) internal returns (bool flipped) {
    ...
    if (liquidityBefore == 0) {
        // 按照惯例，假设所有先前的费用都是在 tick 下方收取的
        // tick 下方
        if (tick <= currentTick) {
            tickInfo.feeGrowthOutside0X128 = feeGrowthGlobal0X128;
            tickInfo.feeGrowthOutside1X128 = feeGrowthGlobal1X128;
        }

        tickInfo.initialized = true;
    }
    ...
}
```

如果它不在当前价格范围内，则其费用跟踪器将为 0，并且它们将在下次 cross tick 时更新（请参阅我们上面更新的 `cross` 函数）。

### 更新仓位费用和代币数量

下一步是计算一个仓位累积的费用和代币。由于一个仓位是两个 tick 之间的范围，我们将使用我们在上一步中添加到 ticks 的费用跟踪器来计算这些值。下一个函数可能看起来很混乱，但它实现了我们之前看到的精确的价格范围费用公式：
```solidity
// src/lib/Tick.sol
function getFeeGrowthInside(
    mapping(int24 => Tick.Info) storage self,
    int24 lowerTick_,
    int24 upperTick_,
    int24 currentTick,
    uint256 feeGrowthGlobal0X128,
    uint256 feeGrowthGlobal1X128
)
    internal
    view
    returns (uint256 feeGrowthInside0X128, uint256 feeGrowthInside1X128)
{
    Tick.Info storage lowerTick = self[lowerTick_];
    Tick.Info storage upperTick = self[upperTick_];

    uint256 feeGrowthBelow0X128;
    uint256 feeGrowthBelow1X128;
    if (currentTick >= lowerTick_) {
        feeGrowthBelow0X128 = lowerTick.feeGrowthOutside0X128;
        feeGrowthBelow1X128 = lowerTick.feeGrowthOutside1X128;
    } else {
        feeGrowthBelow0X128 =
            feeGrowthGlobal0X128 -
            lowerTick.feeGrowthOutside0X128;
        feeGrowthBelow1X128 =
            feeGrowthGlobal1X128 -
            lowerTick.feeGrowthOutside1X128;
    }

    uint256 feeGrowthAbove0X128;
    uint256 feeGrowthAbove1X128;
    if (currentTick < upperTick_) {
        feeGrowthAbove0X128 = upperTick.feeGrowthOutside0X128;
        feeGrowthAbove1X128 = upperTick.feeGrowthOutside1X128;
    } else {
        feeGrowthAbove0X128 =
            feeGrowthGlobal0X128 -
            upperTick.feeGrowthOutside0X128;
        feeGrowthAbove1X128 =
            feeGrowthGlobal1X128 -
            upperTick.feeGrowthOutside1X128;
    }

    feeGrowthInside0X128 =
        feeGrowthGlobal0X128 -
        feeGrowthBelow0X128 -
        feeGrowthAbove0X128;
    feeGrowthInside1X128 =
        feeGrowthGlobal1X128 -
        feeGrowthBelow1X128 -
        feeGrowthAbove1X128;
}
```

在这里，我们计算在两个 tick 之间累积的费用（在一个价格范围内）。为此，我们首先计算在下限 tick 之下累积的费用，然后计算在上限 tick 之上计算的费用。最后，我们从全局累积的费用中减去这些费用。这就是我们之前看到的公式：

$$f_{r} = f_{g} - f_{b}(i_{l}) - f_{a}(i_{u})$$

当计算在 tick 之上和之下收取的费用时，我们根据价格范围是否已激活（当前价格是否在价格范围的边界 tick 之间）以不同的方式进行计算。当它已激活时，我们仅使用 tick 的当前费用跟踪器；当它未激活时，我们需要采用 tick 的更新的费用跟踪器——您可以在上面代码中的两个 `else` 分支中看到这些计算。

在找到在一个仓位内累积的费用后，我们已准备好更新该仓位的费用和代币数量跟踪器：
```solidity
// src/lib/Position.sol
function update(
    Info storage self,
    int128 liquidityDelta,
    uint256 feeGrowthInside0X128,
    uint256 feeGrowthInside1X128
) internal {
    uint128 tokensOwed0 = uint128(
        PRBMath.mulDiv(
            feeGrowthInside0X128 - self.feeGrowthInside0LastX128,
            self.liquidity,
            FixedPoint128.Q128
        )
    );
    uint128 tokensOwed1 = uint128(
        PRBMath.mulDiv(
            feeGrowthInside1X128 - self.feeGrowthInside1LastX128,
            self.liquidity,
            FixedPoint128.Q128
        )
    );

    self.liquidity = LiquidityMath.addLiquidity(
        self.liquidity,
        liquidityDelta
    );
    self.feeGrowthInside0LastX128 = feeGrowthInside0X128;
    self.feeGrowthInside1LastX128 = feeGrowthInside1X128;

    if (tokensOwed0 > 0 || tokensOwed1 > 0) {
        self.tokensOwed0 += tokensOwed0;
        self.tokensOwed1 += tokensOwed1;
    }
}
```

当计算应付代币时，我们将仓位累积的费用乘以流动性——这是我们在交换期间所做的相反操作。最后，我们更新费用跟踪器，并将代币数量添加到先前跟踪的代币数量中。

现在，每当修改一个仓位时（在添加或移除流动性期间），我们都会计算一个仓位收取的费用并更新该仓位：
```solidity
// src/UniswapV3Pool.sol
function mint(...) {
    ...
    bool flippedLower = ticks.update(params.lowerTick, ...);
    bool flippedUpper = ticks.update(params.upperTick, ...);
    ...
    (uint256 feeGrowthInside0X128, uint256 feeGrowthInside1X128) = ticks
        .getFeeGrowthInside(
            params.lowerTick,
            params.upperTick,
            slot0_.tick,
            feeGrowthGlobal0X128_,
            feeGrowthGlobal1X128_
        );

    position.update(
        params.liquidityDelta,
        feeGrowthInside0X128,
        feeGrowthInside1X128
    );
    ...
}
```

## 移除流动性

我们现在准备好添加我们尚未实现的唯一核心功能——移除流动性。与铸造相反，我们将此函数称为 `burn`。此函数将允许流动性提供者从他们先前添加到仓位中移除一部分或全部流动性。除此之外，它还将计算流动性提供者有资格获得的费用代币。但是，代币的实际转移将在一个单独的函数 `collect` 中完成。

### 燃烧流动性

燃烧流动性与铸造相反。我们当前的设计和实现使其成为一项轻松的任务：燃烧流动性只是带有负号的铸造。这就像添加负数的流动性。

> 为了实现 `burn`，我需要重构代码并将与仓位管理相关的所有内容（更新 ticks 和仓位，以及代币数量计算）提取到 `_modifyPosition` 函数中，该函数由 `mint` 和 `burn` 函数使用。

```solidity
function burn(
    int24 lowerTick,
    int24 upperTick,
    uint128 amount
) public returns (uint256 amount0, uint256 amount1) {
    (
        Position.Info storage position,
        int256 amount0Int,
        int256 amount1Int
    ) = _modifyPosition(
            ModifyPositionParams({
                owner: msg.sender,
                lowerTick: lowerTick,
                upperTick: upperTick,
                liquidityDelta: -(int128(amount))
            })
        );

    amount0 = uint256(-amount0Int);
    amount1 = uint256(-amount1Int);

    if (amount0 > 0 || amount1 > 0) {
        (position.tokensOwed0, position.tokensOwed1) = (
            position.tokensOwed0 + uint128(amount0),
            position.tokensOwed1 + uint128(amount1)
        );
    }

    emit Burn(msg.sender, lowerTick, upperTick, amount, amount0, amount1);
}
```

在 `burn` 函数中，我们首先更新一个仓位并从中移除一些流动性。然后，我们更新仓位欠的代币数量——它们现在包括通过费用累积的数量以及先前作为流动性提供的数量。我们也可以将其视为将仓位流动性转换为仓位欠的代币数量——这些数量将不再用作流动性，并且可以通过调用 `collect` 函数自由赎回：

```solidity
function collect(
    address recipient,
    int24 lowerTick,
    int24 upperTick,
    uint128 amount0Requested,
    uint128 amount1Requested
) public returns (uint128 amount0, uint128 amount1) {
    Position.Info storage position = positions.get(
        msg.sender,
        lowerTick,
        upperTick
    );

    amount0 = amount0Requested > position.tokensOwed0
        ? position.tokensOwed0
        : amount0Requested;
    amount1 = amount1Requested > position.tokensOwed1
        ? position.tokensOwed1
        : amount1Requested;

    if (amount0 > 0) {
        position.tokensOwed0 -= amount0;
        IERC20(token0).transfer(recipient, amount0);
    }

    if (amount1 > 0) {
        position.tokensOwed1 -= amount1;
        IERC20(token1).transfer(recipient, amount1);
    }

    emit Collect(
        msg.sender,
        recipient,
        lowerTick,
        upperTick,
        amount0,
        amount1
    );
}
```

此函数仅从池中转移代币，并确保只能转移有效数量（一个人不能转移超过他们燃烧的数量 + 他们获得的费用）。

还有一种仅收取费用而不燃烧流动性的方法：燃烧 0 数量的流动性，然后调