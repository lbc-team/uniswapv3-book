# 管理器合约

在部署我们的池合约之前，我们需要解决一个问题。正如你所记得的，Uniswap V3 合约分为两类：
1. 核心合约，用于实现核心功能，但不提供用户友好的接口。
2. 外围合约，为核心合约实现用户友好的接口。

池合约是一个核心合约，它不应该是用户友好的和灵活的。它期望调用者进行所有计算（价格、数量）并提供正确的调用参数。它也不使用 ERC20 的 `transferFrom` 从调用者处转移代币。相反，它使用两个回调：
1. `uniswapV3MintCallback`，在铸造流动性时调用;
2. `uniswapV3SwapCallback`，在交换代币时调用。

在我们的测试中，我们在测试合约中实现了这些回调。由于只有合约才能实现它们，因此池合约不能被普通用户（非合约地址）调用。这没问题。但现在不行了🙂。

本书的下一步是将池合约部署到本地区块链，并从前端应用程序与之交互。因此，我们需要构建一个合约，让非合约地址能够与池进行交互。现在就开始吧!

## 工作流程

以下是管理器合约的工作方式：
1. 为了铸造流动性，我们将批准将代币花费到管理器合约。
2. 然后我们将调用管理器合约的 `mint` 函数，并将铸造参数以及我们希望提供流动性的池的地址传递给它。
3. 管理器合约将调用池的 `mint` 函数，并将实现 `uniswapV3MintCallback`。它将有权将我们的代币发送到池合约。
4. 为了交换代币，我们还将批准将代币花费到管理器合约。
5. 然后我们将调用管理器合约的 `swap` 函数，与铸造类似，它会将调用传递给池。
管理器合约会将我们的代币发送到池合约，池合约将交换它们，并将输出金额发送给我们。

因此，管理器合约将充当用户和池之间的中介。

## 将数据传递给回调

在实现管理器合约之前，我们需要升级池合约。

管理器合约将与任何池一起工作，并且它将允许任何地址调用它。为了实现这一点，我们需要升级回调：我们希望将不同的池地址和用户地址传递给它们。让我们看看我们当前 `uniswapV3MintCallback` 的实现（在测试合约中）：
```solidity
function uniswapV3MintCallback(uint256 amount0, uint256 amount1) public {
    if (transferInMintCallback) {
        token0.transfer(msg.sender, amount0);
        token1.transfer(msg.sender, amount1);
    }
}
```

这里的关键点：
1. 该函数转移属于测试合约的代币——我们希望它使用 `transferFrom` 转移来自调用者的代币。
2. 该函数知道 `token0` 和 `token1`，它们对于每个池都不同。

想法：我们需要更改回调的参数，以便我们可以传递用户和池地址。

现在，让我们看看交换回调：
```solidity
function uniswapV3SwapCallback(int256 amount0, int256 amount1) public {
    if (amount0 > 0 && transferInSwapCallback) {
        token0.transfer(msg.sender, uint256(amount0));
    }

    if (amount1 > 0 && transferInSwapCallback) {
        token1.transfer(msg.sender, uint256(amount1));
    }
}
```

同样，它从测试合约转移代币，并且它知道 `token0` 和 `token1`。

为了将额外的数据传递给回调，我们需要首先将其传递给 `mint` 和 `swap`（因为回调是从这些函数调用的）。然而，由于这些额外的数据没有在函数中使用，并且为了不使它们的参数更混乱，我们将使用 [abi.encode()](https://docs.soliditylang.org/en/latest/units-and-global-variables.html?highlight=abi.encode#abi-encoding-and-decoding-functions) 对额外的数据进行编码。

让我们将额外的数据定义为一个结构体：
```solidity
// src/UniswapV3Pool.sol
...
struct CallbackData {
    address token0;
    address token1;
    address payer;
}
...
```

然后将编码后的数据传递给回调：
```solidity
function mint(
    address owner,
    int24 lowerTick,
    int24 upperTick,
    uint128 amount,
    bytes calldata data // <--- 新行
) external returns (uint256 amount0, uint256 amount1) {
    ...
    IUniswapV3MintCallback(msg.sender).uniswapV3MintCallback(
        amount0,
        amount1,
        data // <--- 新行
    );
    ...
}

function swap(address recipient, bytes calldata data) // <--- 添加了`data`
    public
    returns (int256 amount0, int256 amount1)
{
    ...
    IUniswapV3SwapCallback(msg.sender).uniswapV3SwapCallback(
        amount0,
        amount1,
        data // <--- 新行
    );
    ...
}
```

现在，我们可以在测试合约的回调中读取额外的数据。
```solidity
function uniswapV3MintCallback(
    uint256 amount0,
    uint256 amount1,
    bytes calldata data
) public {
    if (transferInMintCallback) {
        UniswapV3Pool.CallbackData memory extra = abi.decode(
            data,
            (UniswapV3Pool.CallbackData)
        );

        IERC20(extra.token0).transferFrom(extra.payer, msg.sender, amount0);
        IERC20(extra.token1).transferFrom(extra.payer, msg.sender, amount1);
    }
}
```

尝试自己更新其余代码，如果遇到困难，请随时查看 [此提交](https://github.com/Jeiwan/uniswapv3-code/commit/cda23134fd12a190aaeebe718786545621e16c0e)。

## 实现管理器合约

除了实现回调之外，管理器合约不会做太多事情：它只会将调用重定向到池合约。这是一个非常精简的合约：
```solidity
pragma solidity ^0.8.14;

import "../src/UniswapV3Pool.sol";
import "../src/interfaces/IERC20.sol";

contract UniswapV3Manager {
    function mint(
        address poolAddress_,
        int24 lowerTick,
        int24 upperTick,
        uint128 liquidity,
        bytes calldata data
    ) public {
        UniswapV3Pool(poolAddress_).mint(
            msg.sender,
            lowerTick,
            upperTick,
            liquidity,
            data
        );
    }

    function swap(address poolAddress_, bytes calldata data) public {
        UniswapV3Pool(poolAddress_).swap(msg.sender, data);
    }

    function uniswapV3MintCallback(...) {...}
    function uniswapV3SwapCallback(...) {...}
}
```

回调与测试合约中的回调相同，唯一的区别是由于管理器合约始终转移代币，因此没有 `transferInMintCallback` 和 `transferInSwapCallback` 标志。

好了，我们现在已经完全准备好部署并与前端应用程序集成！
