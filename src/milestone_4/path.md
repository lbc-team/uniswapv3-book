# 兑换路径

假设我们只有以下这些池子：WETH/USDC、USDC/USDT 和 WBTC/USDT。如果我们想将 WETH 兑换为 WBTC，我们需要进行多次兑换（WETH→USDC→USDT→WBTC），因为没有 WETH/WBTC 池子。我们可以手动完成此操作，也可以改进我们的合约来处理这种链式或多池兑换。当然，我们将选择后者！

在进行多池兑换时，我们将前一次兑换的输出发送到下一次兑换的输入。例如：

1. 在 WETH/USDC 池中，我们出售 WETH 并购买 USDC；
2. 在 USDC/USDT 池中，我们出售前一次兑换获得的 USDC 并购买 USDT；
3. 在 WBTC/USDT 池中，我们出售前一个池子获得的 USDT 并购买 WBTC。

我们可以将这一系列操作转化为一个路径：

```
WETH/USDC,USDC/USDT,WBTC/USDT
```

并在我们的合约中迭代此路径，以便在一个交易中执行多次兑换。但是，回想一下前一章，我们不需要知道池子的地址，而是可以从池子的参数中推导出它们。因此，上面的路径可以转化为一系列代币：

```
WETH, USDC, USDT, WBTC
```

回想一下，tick 间距是另一个标识池子的参数（除了代币之外）。因此，上面的路径变为：

```
WETH, 60, USDC, 10, USDT, 60, WBTC
```

其中 60 和 10 是 tick 间距。我们在波动性较大的交易对（例如 ETH/USDC、WBTC/USDT）中使用 60，在稳定币交易对（USDC/USDT）中使用 10。

现在，有了这样的路径，我们可以迭代它来构建每个池子的池参数：

1. `WETH, 60, USDC`;
2. `USDC, 10, USDT`;
3. `USDT, 60, WBTC`.

知道这些参数后，我们可以使用 `PoolAddress.computeAddress` 推导出池子的地址，这是我们在上一章中实现的。

> 我们也可以在单个池子内进行兑换时使用这个概念：路径将只包含一个池子的参数。因此，我们可以普遍地在所有兑换中使用兑换路径。

让我们构建一个库来处理兑换路径。

## 路径库

在代码中，兑换路径是一个字节序列。在 Solidity 中，路径可以像这样构建：
```solidity
bytes.concat(
    bytes20(address(weth)),
    bytes3(uint24(60)),
    bytes20(address(usdc)),
    bytes3(uint24(10)),
    bytes20(address(usdt)),
    bytes3(uint24(60)),
    bytes20(address(wbtc))
);
```

它看起来像这样：
```shell
0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2 # weth 地址
  00003c                                   # 60
  A0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 # usdc 地址
  00000a                                   # 10
  dAC17F958D2ee523a2206206994597C13D831ec7 # usdt 地址
  00003c                                   # 60
  2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599 # wbtc 地址
```

我们需要实现以下函数：
1. 计算路径中的池子数量；
2. 确定路径是否包含多个池子；
3. 从路径中提取第一个池子的参数；
4. 前进到路径中的下一个交易对；
5. 以及解码第一个池子的参数。

### 计算路径中的池子数量
让我们从计算路径中的池子数量开始：
```solidity
// src/lib/Path.sol
library Path {
    /// @dev The length the bytes encoded address
    uint256 private constant ADDR_SIZE = 20;
    /// @dev The length the bytes encoded tick spacing
    uint256 private constant TICKSPACING_SIZE = 3;

    /// @dev The offset of a single token address + tick spacing
    uint256 private constant NEXT_OFFSET = ADDR_SIZE + TICKSPACING_SIZE;
    /// @dev The offset of an encoded pool key (tokenIn + tick spacing + tokenOut)
    uint256 private constant POP_OFFSET = NEXT_OFFSET + ADDR_SIZE;
    /// @dev The minimum length of a path that contains 2 or more pools;
    uint256 private constant MULTIPLE_POOLS_MIN_LENGTH =
        POP_OFFSET + NEXT_OFFSET;

    ...
```

我们首先定义几个常量：
1. `ADDR_SIZE` 是地址的大小，20 字节；
2. `TICKSPACING_SIZE` 是 tick 间距的大小，3 字节 (`uint24`)；
3. `NEXT_OFFSET` 是下一个代币地址的偏移量——要获得它，我们跳过一个地址和一个 tick 间距；
4. `POP_OFFSET` 是池子密钥（代币地址 + tick 间距 + 代币地址）的偏移量；
5. `MULTIPLE_POOLS_MIN_LENGTH` 是包含 2 个或更多池子的路径的最小长度（一组池子参数 + tick 间距 + 代币地址）。

要计算路径中的池子数量，我们减去地址的大小（路径中的第一个或最后一个代币），并将剩余部分除以 `NEXT_OFFSET` (地址 + tick 间距)：

```solidity
function numPools(bytes memory path) internal pure returns (uint256) {
    return (path.length - ADDR_SIZE) / NEXT_OFFSET;
}
```

### 确定路径是否包含多个池子
要检查路径中是否存在多个池子，我们需要将路径的长度与 `MULTIPLE_POOLS_MIN_LENGTH` 进行比较：

```solidity
function hasMultiplePools(bytes memory path) internal pure returns (bool) {
    return path.length >= MULTIPLE_POOLS_MIN_LENGTH;
}
```

### 从路径中提取第一个池子的参数

为了实现其他函数，我们需要一个辅助库，因为 Solidity 本身没有字节操作函数。具体来说，我们需要一个从字节数组中提取子数组的函数，以及几个将字节转换为 `address` 和 `uint24` 的函数。

幸运的是，有一个很棒的开源库叫做 [solidity-bytes-utils](https://github.com/GNSPS/solidity-bytes-utils)。要使用该库，我们需要在 `Path` 库中扩展 `bytes` 类型：
```solidity
library Path {
    using BytesLib for bytes;
    ...
}
```

我们现在可以实现 `getFirstPool` 了：
```solidity
function getFirstPool(bytes memory path)
    internal
    pure
    returns (bytes memory)
{
    return path.slice(0, POP_OFFSET);
}
```

该函数只是返回第一个编码为字节的 “代币地址 + tick 间距 + 代币地址” 段。

### 前进到路径中的下一个交易对

当我们迭代路径并丢弃已处理的池子时，我们将使用下一个函数。请注意，我们正在删除 “代币地址 + tick 间距”，而不是完整的池参数，因为我们需要另一个代币地址来计算下一个池子的地址。

```solidity
function skipToken(bytes memory path) internal pure returns (bytes memory) {
    return path.slice(NEXT_OFFSET, path.length - NEXT_OFFSET);
}
```

### 解码第一个池子的参数

最后，我们需要解码路径中第一个池子的参数：

```solidity
function decodeFirstPool(bytes memory path)
    internal
    pure
    returns (
        address tokenIn,
        address tokenOut,
        uint24 tickSpacing
    )
{
    tokenIn = path.toAddress(0);
    tickSpacing = path.toUint24(ADDR_SIZE);
    tokenOut = path.toAddress(NEXT_OFFSET);
}
```

不幸的是，`BytesLib` 没有实现 `toUint24` 函数，但我们可以自己实现它！ `BytesLib` 有多个 `toUintXX` 函数，所以我们可以选择其中一个并将其转换为 `uint24`：
```solidity
library BytesLibExt {
    function toUint24(bytes memory _bytes, uint256 _start)
        internal
        pure
        returns (uint24)
    {
        require(_bytes.length >= _start + 3, "toUint24_outOfBounds");
        uint24 tempUint;

        assembly {
            tempUint := mload(add(add(_bytes, 0x3), _start))
        }

        return tempUint;
    }
}
```

我们正在一个新的库合约中执行此操作，然后我们可以在 `Path` 库中与 `BytesLib` 一起使用它：

```solidity
library Path {
    using BytesLib for bytes;
    using BytesLibExt for bytes;
    ...
}
```