## 闪电贷

Uniswap V2 和 V3 都实现了闪电贷：无限制且无抵押的贷款，必须在同一笔交易中偿还。资金池向用户提供他们请求的任意数量的代币，但是，在调用结束时，必须偿还这些金额，并支付少量费用。

闪电贷必须在同一笔交易中偿还，这意味着普通用户无法使用闪电贷：作为用户，你无法在交易中编写自定义逻辑。闪电贷只能由智能合约获取和偿还。

闪电贷是 DeFi 中一种强大的金融工具。虽然它经常被用来利用 DeFi 协议中的漏洞（通过膨胀资金池余额和滥用有缺陷的状态管理），但它也有许多好的应用（例如，在借贷协议上进行杠杆头寸管理）——这就是为什么存储流动性的 DeFi 应用提供无需许可的闪电贷。

### 实现闪电贷

在 Uniswap V2 中，闪电贷是交换功能的一部分：可以在交换期间借用代币，但你必须在同一笔交易中归还它们或等量的其他资金池代币。在 V3 中，闪电贷与交换分离——它只是一个函数，向调用者提供他们请求的代币数量，在调用者上调用回调，并确保闪电贷已偿还：

```solidity
function flash(
    uint256 amount0,
    uint256 amount1,
    bytes calldata data
) public {
    uint256 balance0Before = IERC20(token0).balanceOf(address(this));
    uint256 balance1Before = IERC20(token1).balanceOf(address(this));

    if (amount0 > 0) IERC20(token0).transfer(msg.sender, amount0);
    if (amount1 > 0) IERC20(token1).transfer(msg.sender, amount1);

    IUniswapV3FlashCallback(msg.sender).uniswapV3FlashCallback(data);

    require(IERC20(token0).balanceOf(address(this)) >= balance0Before);
    require(IERC20(token1).balanceOf(address(this)) >= balance1Before);

    emit Flash(msg.sender, amount0, amount1);
}
```

该函数将代币发送给调用者，然后在调用者上调用 `uniswapV3FlashCallback`——这是调用者应偿还贷款的地方。然后，该函数确保其余额没有减少。请注意，允许将自定义数据传递给回调。

这是一个回调实现的示例：

```solidity
function uniswapV3FlashCallback(bytes calldata data) public {
    (uint256 amount0, uint256 amount1) = abi.decode(
        data,
        (uint256, uint256)
    );

    if (amount0 > 0) token0.transfer(msg.sender, amount0);
    if (amount1 > 0) token1.transfer(msg.sender, amount1);
}
```

在此实现中，我们只是将代币发送回资金池（我在 `flash` 函数测试中使用了此回调）。 实际上，它可以使用借入的金额在其他 DeFi 协议上执行一些操作。 但它始终必须在此回调中偿还贷款。

就是这样！
