# 协议费用

在进行 Uniswap 实现的过程中，您可能已经问过自己，“Uniswap 是如何赚钱的？” 嗯，它并没有（至少截至 2022 年 9 月）。

在我们目前构建的实现中，交易者向流动性提供者支付提供流动性的费用，而作为开发 DEX 的公司的 Uniswap Labs 并不参与这个过程。无论是交易者还是流动性提供者，都不会因为使用 Uniswap DEX 而向 Uniswap Labs 付费。这是为什么呢？

Uniswap Labs 有一种方法可以开始通过 DEX 赚钱。但是，该机制尚未启用（同样，截至 2022 年 9 月）。每个 Uniswap 池都有一个*协议费用*收集机制。协议费用从交换费用中收取：交换费用的一小部分被扣除并保存为协议费用，供以后由 Factory 合约所有者 (Uniswap Labs) 收取。协议费用的规模预计将由 UNI 代币持有者决定，但必须是交换费用的 $1/4$ 到 $1/10$（含）。

为简洁起见，我们不会将协议费用添加到我们的实现中，但让我们看看它们在 Uniswap 中是如何实现的。

协议费用大小存储在 `slot0` 中：

```solidity
// UniswapV3Pool.sol
struct Slot0 {
    ...
    // 当前协议费用，表示为提款时收取的交换费用的百分比
    // 表示为整数分母 (1/x)%
    uint8 feeProtocol;
    ...
}
```

需要一个全局累加器来跟踪应计费用：
```solidity
// 以 token0/token1 单位累计的协议费用
struct ProtocolFees {
    uint128 token0;
    uint128 token1;
}
ProtocolFees public override protocolFees;
```

协议费用在 `setFeeProtocol` 函数中设置：

```solidity
function setFeeProtocol(uint8 feeProtocol0, uint8 feeProtocol1) external override lock onlyFactoryOwner {
    require(
        (feeProtocol0 == 0 || (feeProtocol0 >= 4 && feeProtocol0 <= 10)) &&
            (feeProtocol1 == 0 || (feeProtocol1 >= 4 && feeProtocol1 <= 10))
    );
    uint8 feeProtocolOld = slot0.feeProtocol;
    slot0.feeProtocol = feeProtocol0 + (feeProtocol1 << 4);
    emit SetFeeProtocol(feeProtocolOld % 16, feeProtocolOld >> 4, feeProtocol0, feeProtocol1);
}
```

正如你所看到的，允许为每个代币单独设置协议费用。这些值是两个 `uint8`，它们被打包存储在一个 `uint8` 中：`feeProtocol1` 向左移动 4 位（这等同于将其乘以 16）并添加到 `feeProtocol0`。要解包 `feeProtocol0`，需要取 `slot0.feeProtocol` 除以 16 的余数；`feeProtocol1` 只是将 `slot0.feeProtocol` 向右移动 4 位。这种打包方式有效，因为 `feeProtocol0` 和 `feeProtocol1` 都不可能大于 10。

在开始交换之前，我们需要根据交换方向选择其中一种协议费用（交换费用和协议费用在输入代币上收取）：

```solidity
function swap(...) {
    ...
    uint8 feeProtocol = zeroForOne ? (slot0_.feeProtocol % 16) : (slot0_.feeProtocol >> 4);
    ...
```

为了累积协议费用，我们在计算交换步骤金额后立即从交换费用中扣除它们：

```solidity
...
while (...) {
    (..., step.feeAmount) = SwapMath.computeSwapStep(...);

    if (cache.feeProtocol > 0) {
        uint256 delta = step.feeAmount / cache.feeProtocol;
        step.feeAmount -= delta;
        state.protocolFee += uint128(delta);
    }

    ...
}
...
```

完成交换后，需要更新全局协议费用累加器：
```solidity
if (zeroForOne) {
    if (state.protocolFee > 0) protocolFees.token0 += state.protocolFee;
} else {
    if (state.protocolFee > 0) protocolFees.token1 += state.protocolFee;
}
```

最后，Factory 合约所有者可以通过调用 `collectProtocol` 来收集应计的协议费用：

```solidity
function collectProtocol(
    address recipient,
    uint128 amount0Requested,
    uint128 amount1Requested
) external override lock onlyFactoryOwner returns (uint128 amount0, uint128 amount1) {
    amount0 = amount0Requested > protocolFees.token0 ? protocolFees.token0 : amount0Requested;
    amount1 = amount1Requested > protocolFees.token1 ? protocolFees.token1 : amount1Requested;

    if (amount0 > 0) {
        if (amount0 == protocolFees.token0) amount0--;
        protocolFees.token0 -= amount0;
        TransferHelper.safeTransfer(token0, recipient, amount0);
    }
    if (amount1 > 0) {
        if (amount1 == protocolFees.token1) amount1--;
        protocolFees.token1 -= amount1;
        TransferHelper.safeTransfer(token1, recipient, amount1);
    }

    emit CollectProtocol(msg.sender, recipient, amount0, amount1);
}
```