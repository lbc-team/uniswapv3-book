# Quoter 合约

为了将我们更新后的 Pool 合约集成到前端应用中，我们需要一种无需进行实际兑换即可计算兑换数量的方法。用户将输入他们想要出售的数量，我们希望计算并向他们展示他们将获得的兑换数量。我们将通过 Quoter 合约来实现这一点。

由于 Uniswap V3 中的流动性分散在多个价格范围内，我们无法使用公式计算兑换数量（这在 Uniswap V2 中是可行的）。Uniswap V3 的设计迫使我们使用不同的方法：为了计算兑换数量，我们将启动一次真实的兑换，并在回调函数中中断它，获取由 Pool 合约计算的数量。也就是说，我们必须模拟一次真实的兑换来计算输出数量！

同样，我们将为此创建一个辅助合约：

```solidity
contract UniswapV3Quoter {
    struct QuoteParams {
        address pool;
        uint256 amountIn;
        bool zeroForOne;
    }

    function quote(QuoteParams memory params)
        public
        returns (
            uint256 amountOut,
            uint160 sqrtPriceX96After,
            int24 tickAfter
        )
    {
        ...
```

Quoter 是一个仅实现一个公共函数 `quote` 的合约。Quoter 是一个通用的合约，它可以与任何池子一起使用，因此它将池子地址作为参数。其他参数（`amountIn` 和 `zeroForOne`）是模拟兑换所必需的。

```solidity
try
    IUniswapV3Pool(params.pool).swap(
        address(this),
        params.zeroForOne,
        params.amountIn,
        abi.encode(params.pool)
    )
{} catch (bytes memory reason) {
    return abi.decode(reason, (uint256, uint160, int24));
}
```

合约唯一做的事情是调用池子的 `swap` 函数。预计此调用会 revert（即抛出一个错误）——我们将在 swap 回调中执行此操作。在 revert 的情况下，revert 的原因将被解码并返回；`quote` 永远不会 revert。请注意，在额外的数据中，我们只传递了池子地址——在 swap 回调中，我们将使用它来获取 swap 后的池子的 `slot0`。

```solidity
function uniswapV3SwapCallback(
    int256 amount0Delta,
    int256 amount1Delta,
    bytes memory data
) external view {
    address pool = abi.decode(data, (address));

    uint256 amountOut = amount0Delta > 0
        ? uint256(-amount1Delta)
        : uint256(-amount0Delta);

    (uint160 sqrtPriceX96After, int24 tickAfter) = IUniswapV3Pool(pool)
        .slot0();
```

在 swap 回调中，我们收集了我们需要的数值：输出数量、新价格和相应的 tick。接下来，我们需要保存这些值并 revert：

```solidity
assembly {
    let ptr := mload(0x40)
    mstore(ptr, amountOut)
    mstore(add(ptr, 0x20), sqrtPriceX96After)
    mstore(add(ptr, 0x40), tickAfter)
    revert(ptr, 96)
}
```

为了优化 gas，这一部分是用 [Yul](https://docs.soliditylang.org/en/latest/assembly.html) 实现的，Yul 是用于 Solidity 中内联汇编的语言。让我们分解一下：
1. `mload(0x40)` 读取下一个可用内存槽的指针（EVM 中的内存以 32 字节的槽组织）；
1. 在该内存槽中，`mstore(ptr, amountOut)` 写入 `amountOut`；
1. `mstore(add(ptr, 0x20), sqrtPriceX96After)` 在 `amountOut` 之后立即写入 `sqrtPriceX96After`；
1. `mstore(add(ptr, 0x40), tickAfter)` 在 `sqrtPriceX96After` 之后写入 `tickAfter`；
1. `revert(ptr, 96)` revert 该调用，并返回地址 `ptr` 处 96 字节的数据（我们写入内存的值的总长度）（我们上面写入的数据的开头）。

因此，我们将所需的值的字节表示形式连接起来（完全是 `abi.encode()` 所做的）。请注意，偏移量始终为 32 字节，即使 `sqrtPriceX96After` 占用 20 字节（`uint160`）且 `tickAfter` 占用 3 字节（`int24`）。这是为了我们可以使用 `abi.decode()` 解码数据：它的对应项 `abi.encode()` 将所有整数编码为 32 字节的 words。

然后... ~它消失了~ 完成了。

## 概括

让我们概括一下以更好地理解该算法：
1. `quote` 使用输入数量和兑换方向调用池子的 `swap`；
1. `swap` 执行一次真实的兑换，它运行循环以填充用户指定的输入数量；
1. 为了从用户那里获取 token，`swap` 在调用者上调用 swap 回调；
1. 调用者（Quoter 合约）实现回调，在回调中，它以输出数量、新价格和新 tick 进行 revert；
1. revert 冒泡到最初的 `quote` 调用；
1. 在 `quote` 中，revert 被捕获，revert 原因被解码并作为调用 `quote` 的结果返回。

我希望这很清楚！

## Quoter 限制

这种设计有一个显着的限制：由于 `quote` 调用 Pool 合约的 `swap` 函数，并且 `swap` 函数不是 pure 或 view 函数（因为它会修改合约状态），因此 `quote` 也不能是 pure 或 view。`swap` 修改状态，`quote` 也是如此，即使不是在 Quoter 合约中。但是我们将 `quote` 视为 getter，一个仅读取合约数据的函数。这种不一致意味着当调用 `quote` 时，EVM 将使用 [CALL](https://www.evm.codes/#f1) 操作码而不是 [STATICCALL](https://www.evm.codes/#fa)。这不是一个大问题，因为 Quoter 在 swap 回调中 revert，并且 revert 会重置在调用期间修改的状态——这保证了 `quote` 不会修改 Pool 合约的状态（不会发生实际的交易）。

由此问题带来的另一个不便是，从客户端库（Ethers.js、Web3.js 等）调用 `quote` 将触发一个 transaction。为了解决这个问题，我们需要强制库进行静态调用。我们将在本里程碑后面的 Ethers.js 中看到如何执行此操作。
