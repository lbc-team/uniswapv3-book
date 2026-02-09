# 首次 Swap

既然我们有了流动性，我们就可以进行首次 swap 了！

## 计算 Swap 数量

当然，第一步是弄清楚如何计算 swap 数量。同样，让我们选择并硬编码一些我们要交易的 USDC 数量来换取 ETH。就定为 42 吧！我们将用 42 USDC 购买 ETH。

在确定我们要出售的 token 数量后，我们需要计算我们将获得的交换 token 数量。在 Uniswap V2 中，我们本可以使用当前的池储备，但在 Uniswap V3 中，我们有 $L$ 和 $\sqrt{P}$，并且我们知道，当在价格范围内进行 swap 时，只有 $\sqrt{P}$ 会发生变化，$L$ 保持不变（当 swap 仅在一个价格范围内完成时，Uniswap V3 的行为与 V2 完全相同）。我们还知道：

$$L = \frac{\Delta y}{\Delta \sqrt{P}}$$

并且...我们知道 $\Delta y$！这就是我们要交易的 42 USDC！因此，我们可以找到在给定 $L$ 的情况下，出售 42 USDC 将如何影响当前的 $\sqrt{P}$：

$$\Delta \sqrt{P} = \frac{\Delta y}{L}$$

在 Uniswap V3 中，我们选择**我们希望交易导致的价格**（回想一下，swap 会改变当前价格，即它会沿着曲线移动当前价格）。知道了目标价格，合约将计算它需要从我们这里获取的输入 token 数量以及它将给我们的相应的输出 token 数量。

让我们将我们的数字代入上面的公式：

$$\Delta \sqrt{P} = \frac{42 \enspace USDC}{1517882343751509868544} = 2192253463713690532467206957$$

将此添加到当前的 $\sqrt{P}$ 之后，我们将得到目标价格：

$$\sqrt{P_{target}} = \sqrt{P_{current}} + \Delta \sqrt{P}$$

$$\sqrt{P_{target}} = 5604469350942327889444743441197$$

> 在 Python 中计算目标价格：
> ```python
> amount_in = 42 * eth
> price_diff = (amount_in * q96) // liq
> price_next = sqrtp_cur + price_diff
> print("New price:", (price_next / q96) ** 2)
> print("New sqrtP:", price_next)
> print("New tick:", price_to_tick((price_next / q96) ** 2))
> # New price: 5003.913912782393
> # New sqrtP: 5604469350942327889444743441197
> # New tick: 85184
> ```

在找到目标价格后，我们可以使用前一章中的数量计算函数来计算 token 数量：

$$ x = \frac{L(\sqrt{p_b}-\sqrt{p_a})}{\sqrt{p_b}\sqrt{p_a}}$$
$$ y = L(\sqrt{p_b}-\sqrt{p_a}) $$

> 在 Python 中：
> ```python
> amount_in = calc_amount1(liq, price_next, sqrtp_cur)
> amount_out = calc_amount0(liq, price_next, sqrtp_cur)
> 
> print("USDC in:", amount_in / eth)
> print("ETH out:", amount_out / eth)
> # USDC in: 42.0
> # ETH out: 0.008396714242162444
> ```

为了验证数量，让我们回顾一下另一个公式：

$$\Delta x = \Delta \frac{1}{\sqrt{P}} L$$

使用此公式，我们可以找到我们购买的 ETH 数量，$\Delta x$，知道价格变化 $\Delta\frac{1}{\sqrt{P}}$ 和流动性 $L$。但请注意：$\Delta \frac{1}{\sqrt{P}}$ 不是 $\frac{1}{\Delta \sqrt{P}}$！前者是 ETH 价格的变化，可以使用以下表达式找到：

$$\Delta \frac{1}{\sqrt{P}} = \frac{1}{\sqrt{P_{target}}} - \frac{1}{\sqrt{P_{current}}}$$

幸运的是，我们已经知道所有值，所以我们可以立即将它们代入（这可能不适合您的屏幕！）：

$$\Delta \frac{1}{\sqrt{P}} = \frac{1}{5604469350942327889444743441197} - \frac{1}{5602277097478614198912276234240}$$

$$= -6.982190286589445\text{e-}35 * 2^{96} $$
$$= -0.00000553186106731426$$

现在，让我们找到 $\Delta x$：

$$\Delta x = -0.00000553186106731426 * 1517882343751509868544 = -8396714242162698 $$

也就是 0.008396714242162698 ETH，并且非常接近我们上面找到的数量！请注意，此数量为负数，因为我们正在将其从池中移除。

## 实现 Swap

Swap 在 `swap` 函数中实现：
```solidity
function swap(address recipient)
    public
    returns (int256 amount0, int256 amount1)
{
    ...
```
目前，它只接受一个接收者，即 token 的接收方。

首先，我们需要找到目标价格和 tick，并计算 token 数量。同样，我们将简单地硬编码我们之前计算的值，以尽可能保持简单：
```solidity
...
int24 nextTick = 85184;
uint160 nextPrice = 5604469350942327889444743441197;

amount0 = -0.008396714242162444 ether;
amount1 = 42 ether;
...
```

接下来，我们需要更新当前的 tick 和 `sqrtP`，因为交易会影响当前价格：
```solidity
...
(slot0.tick, slot0.sqrtPriceX96) = (nextTick, nextPrice);
...
```

接下来，合约将 token 发送给接收者，并让调用者将输入数量转入合约：
```solidity
...
IERC20(token0).transfer(recipient, uint256(-amount0));

uint256 balance1Before = balance1();
IUniswapV3SwapCallback(msg.sender).uniswapV3SwapCallback(
    amount0,
    amount1
);
if (balance1Before + uint256(amount1) < balance1())
    revert InsufficientInputAmount();
...
```

同样，我们使用回调将控制权传递给调用者，并让它转移 token。之后，我们检查池的余额是否正确，并且包含输入数量。

最后，合约发出一个 `Swap` 事件，以使 swap 可被发现。该事件包含有关 swap 的所有信息：
```solidity
...
emit Swap(
    msg.sender,
    recipient,
    amount0,
    amount1,
    slot0.sqrtPriceX96,
    liquidity,
    slot0.tick
);
```

就是这样！该函数只是将一定数量的 token 发送到指定的接收者地址，并期望以交换一定数量的其他 token。在本书中，该函数将变得更加复杂。

## 测试 Swap

现在，我们可以测试 swap 函数。在同一个测试文件中，创建 `testSwapBuyEth` 函数并设置测试用例。此测试用例使用与 `testMintSuccess` 相同的参数：
```solidity
function testSwapBuyEth() public {
    TestCaseParams memory params = TestCaseParams({
        wethBalance: 1 ether,
        usdcBalance: 5000 ether,
        currentTick: 85176,
        lowerTick: 84222,
        upperTick: 86129,
        liquidity: 1517882343751509868544,
        currentSqrtP: 5602277097478614198912276234240,
        shouldTransferInCallback: true,
        mintLiqudity: true
    });
    (uint256 poolBalance0, uint256 poolBalance1) = setupTestCase(params);

    ...
```

但是，接下来的步骤将有所不同。

> 我们不会测试流动性是否已正确添加到池中，因为我们在其他测试用例中测试了此功能。

为了进行测试 swap，我们需要 42 USDC：
```solidity
token1.mint(address(this), 42 ether);
```

在进行 swap 之前，我们需要确保我们可以在池合约请求时将 token 转移到该合约：
```solidity
function uniswapV3SwapCallback(int256 amount0, int256 amount1) public {
    if (amount0 > 0) {
        token0.transfer(msg.sender, uint256(amount0));
    }

    if (amount1 > 0) {
        token1.transfer(msg.sender, uint256(amount1));
    }
}
```
由于 swap 期间的数量可以是正数（发送到池中的数量）和负数（从池中取出的数量），因此在回调中，我们只想发送正数，即我们交易的数量。

现在，我们可以调用 `swap`：
```solidity
(int256 amount0Delta, int256 amount1Delta) = pool.swap(address(this));
```

该函数返回 swap 中使用的 token 数量，我们可以立即检查它们：
```solidity
assertEq(amount0Delta, -0.008396714242162444 ether, "invalid ETH out");
assertEq(amount1Delta, 42 ether, "invalid USDC in");
```

然后，我们需要确保 token 已从调用者处转移：
```solidity
assertEq(
    token0.balanceOf(address(this)),
    uint256(userBalance0Before - amount0Delta),
    "invalid user ETH balance"
);
assertEq(
    token1.balanceOf(address(this)),
    0,
    "invalid user USDC balance"
);
```

并发送到池合约：
```solidity
assertEq(
    token0.balanceOf(address(pool)),
    uint256(int256(poolBalance0) + amount0Delta),
    "invalid pool ETH balance"
);
assertEq(
    token1.balanceOf(address(pool)),
    uint256(int256(poolBalance1) + amount1Delta),
    "invalid pool USDC balance"
);
```

最后，我们检查池状态是否已正确更新：
```solidity
(uint160 sqrtPriceX96, int24 tick) = pool.slot0();
assertEq(
    sqrtPriceX96,
    5604469350942327889444743441197,
    "invalid current sqrtP"
);
assertEq(tick, 85184, "invalid current tick");
assertEq(
    pool.liquidity(),
    1517882343751509868544,
    "invalid current liquidity"
);
```

请注意，swap 不会更改当前的流动性——在后面的章节中，我们将看到它何时会更改。

## 家庭作业

编写一个测试，该测试会因 `InsufficientInputAmount` 错误而失败。请记住，这里有一个隐藏的错误 🙂
