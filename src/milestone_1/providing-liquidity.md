# 提供流动性

理论讲够了，让我们开始编码吧！

创建一个新文件夹（我的叫做 `uniswapv3-code`)，并在其中运行 `forge init --vscode` —— 这将初始化一个 Forge 项目。`--vscode` 标志告诉 Forge 为 Forge 项目配置 Solidity 扩展。

接下来，移除默认的合约及其测试：
- `script/Contract.s.sol`
- `src/Contract.sol`
- `test/Contract.t.sol`

就这样！让我们创建我们的第一个合约！

## Pool 合约

正如你从简介中所了解的那样，Uniswap 部署了多个 Pool 合约，每个合约都是一对代币的交易市场。Uniswap 将所有合约分为两类：

- core 合约，
- 和 periphery 合约。

Core 合约，顾名思义，是实现核心逻辑的合约。这些是最小的、对用户**不**友好的、底层的合约。它们的目的是做一件事，并尽可能可靠和安全地完成它。在 Uniswap V3 中，有 2 个这样的合约：
1. Pool 合约，它实现了一个去中心化交易所的核心逻辑。
2. Factory 合约，它作为 Pool 合约的注册表，也是一个使 Pool 部署更容易的合约。

我们将从 Pool 合约开始，它实现了 Uniswap 的 99% 的核心功能。

创建 `src/UniswapV3Pool.sol`：

```solidity
pragma solidity ^0.8.14;

contract UniswapV3Pool {}
```

让我们思考一下合约将存储哪些数据：
1. 由于每个 Pool 合约都是两个代币的交易市场，我们需要跟踪这两个代币地址。这些地址将是静态的，在 Pool 部署期间一次且永远地设置（因此，它们将是 immutable 的）。
2. 每个 Pool 合约都是一组流动性头寸。我们将它们存储在一个映射中，其中键是唯一的头寸标识符，值是保存有关头寸信息的结构体。
3. 每个 Pool 合约还需要维护一个 ticks 注册表——这将是一个映射，键是 tick 索引，值是存储有关 ticks 信息的结构体。
4. 由于 tick 范围是有限的，我们需要将限制存储在合约中，作为常量。
5. 回想一下，Pool 合约存储流动性数量，$L$。因此我们需要一个变量来存储它。
6. 最后，我们需要跟踪当前价格和相关的 tick。我们会将它们存储在一个 storage slot 中来优化 gas 消耗：这些变量会经常一起读取和写入，因此利用 [Solidity 的状态变量打包特性](https://docs.soliditylang.org/en/v0.8.17/internals/layout_in_storage.html) 是有意义的。

总而言之，这是我们开始的内容：

```solidity
// src/lib/Tick.sol
library Tick {
    struct Info {
        bool initialized;
        uint128 liquidity;
    }
    ...
}

// src/lib/Position.sol
library Position {
    struct Info {
        uint128 liquidity;
    }
    ...
}

// src/UniswapV3Pool.sol
contract UniswapV3Pool {
    using Tick for mapping(int24 => Tick.Info);
    using Position for mapping(bytes32 => Position.Info);
    using Position for Position.Info;

    int24 internal constant MIN_TICK = -887272;
    int24 internal constant MAX_TICK = -MIN_TICK;

    // Pool tokens, immutable
    address public immutable token0;
    address public immutable token1;

    // Packing variables that are read together
    struct Slot0 {
        // Current sqrt(P)
        uint160 sqrtPriceX96;
        // Current tick
        int24 tick;
    }
    Slot0 public slot0;

    // Amount of liquidity, L.
    uint128 public liquidity;

    // Ticks info
    mapping(int24 => Tick.Info) public ticks;
    // Positions info
    mapping(bytes32 => Position.Info) public positions;

    ...
```

Uniswap V3 使用了很多辅助合约，`Tick` 和 `Position` 是其中两个。`using A for B` 是 Solidity 的一个特性，它允许你用库合约 `A` 中的函数扩展类型 `B`。这简化了管理复杂数据结构的过程。

> 为了简洁起见，我将省略对 Solidity 语法和特性的详细解释。Solidity 有 [很棒的文档](https://docs.soliditylang.org/en/latest/)，如果有什么不清楚的地方，请随时参考它！

然后，我们将在构造函数中初始化一些变量：

```solidity
    constructor(
        address token0_,
        address token1_,
        uint160 sqrtPriceX96,
        int24 tick
    ) {
        token0 = token0_;
        token1 = token1_;

        slot0 = Slot0({sqrtPriceX96: sqrtPriceX96, tick: tick});
    }
}
```

在这里，我们设置了 token address immutables，并设置了当前价格和tick——我们不需要为后者提供流动性。

这是我们的起点，本章的目标是使用预先计算的和硬编码的值来进行我们的第一次交换。

## Minting

在 Uniswap V2 中提供流动性的过程称为 *minting*。原因是 V2 Pool 合约会 mint 代币（LP 代币）以换取流动性。V3 不会这样做，但它仍然使用相同的名称来命名该函数。我们也使用它：

```solidity
function mint(
    address owner,
    int24 lowerTick,
    int24 upperTick,
    uint128 amount
) external returns (uint256 amount0, uint256 amount1) {
    ...
```

我们的 `mint` 函数将接收：
1. Owner 的地址，用于跟踪流动性的所有者。
2. 上下限 tick，用于设置价格范围的界限。
3. 我们想要提供的流动性数量。

> 请注意，用户指定的是 $L$，而不是实际的代币数量。当然，这不是很方便，但请回想一下 Pool 合约是一个 core 合约——它不打算对用户友好，因为它应该只实现核心逻辑。在后面的章节中，我们将制作一个辅助合约，该合约将在调用 `Pool.mint` 之前将代币数量转换为 $L$。

让我们概述一下 minting 的工作原理：
1. 用户指定价格范围和流动性数量；
2. 合约更新 `ticks` 和 `positions` 映射；
3. 合约计算用户必须发送的代币数量（我们将预先计算并硬编码它们）；
4. 合约从用户那里获取代币，并验证设置了正确的数量。

让我们从检查 ticks 开始：
```solidity
if (
    lowerTick >= upperTick ||
    lowerTick < MIN_TICK ||
    upperTick > MAX_TICK
) revert InvalidTickRange();
```

并确保提供了某个数量的流动性：
```solidity
if (amount == 0) revert ZeroLiquidity();
```

然后，添加一个 tick 和一个 position：
```solidity
ticks.update(lowerTick, amount);
ticks.update(upperTick, amount);

Position.Info storage position = positions.get(
    owner,
    lowerTick,
    upperTick
);
position.update(amount);
```

`ticks.update` 函数是：

```solidity
// src/lib/Tick.sol
function update(
    mapping(int24 => Tick.Info) storage self,
    int24 tick,
    uint128 liquidityDelta
) internal {
    Tick.Info storage tickInfo = self[tick];
    uint128 liquidityBefore = tickInfo.liquidity;
    uint128 liquidityAfter = liquidityBefore + liquidityDelta;

    if (liquidityBefore == 0) {
        tickInfo.initialized = true;
    }

    tickInfo.liquidity = liquidityAfter;
}
```

如果一个 tick 的 liquidity 为 0，它会初始化该 tick，并向其中添加新的流动性。正如你所看到的，我们在上下限的 tick 上都调用了这个函数，因此流动性被添加到它们两者中。

`position.update` 函数是：
```solidity
// src/libs/Position.sol
function update(Info storage self, uint128 liquidityDelta) internal {
    uint128 liquidityBefore = self.liquidity;
    uint128 liquidityAfter = liquidityBefore + liquidityDelta;

    self.liquidity = liquidityAfter;
}
```
与tick update函数类似，它将流动性添加到特定 position。要获得一个 position，我们调用：
```solidity
// src/libs/Position.sol
...
function get(
    mapping(bytes32 => Info) storage self,
    address owner,
    int24 lowerTick,
    int24 upperTick
) internal view returns (Position.Info storage position) {
    position = self[
        keccak256(abi.encodePacked(owner, lowerTick, upperTick))
    ];
}
...
```

每个 position 由三个键唯一标识：owner address、下限 tick 索引和上限 tick 索引。我们对这三个键进行哈希处理，以降低存储数据的成本：当进行哈希处理时，每个键将占用 32 字节，而不是当 `owner`、`lowerTick` 和 `upperTick` 是单独的键时占用的 96 字节。

> 如果我们使用三个键，我们需要三个映射。每个键都会单独存储，并且会占用 32 字节，因为 Solidity 将值存储在 32 字节的 slot 中（当不应用打包时）。

接下来，继续进行 minting，我们需要计算用户必须存入的数量。幸运的是，我们已经在上一部分中计算出了公式并计算出了确切的数量。所以，我们将硬编码它们：

```solidity
amount0 = 0.998976618347425280 ether;
amount1 = 5000 ether;
```

> 我们将在后面的章节中用实际计算替换这些值。

我们还将根据正在添加的 `amount` 更新 Pool 的 `liquidity`。

```solidity
liquidity += uint128(amount);
```

现在，我们准备从用户那里获取代币。这是通过回调完成的：
```solidity
function mint(...) ... {
    ...

    uint256 balance0Before;
    uint256 balance1Before;
    if (amount0 > 0) balance0Before = balance0();
    if (amount1 > 0) balance1Before = balance1();
    IUniswapV3MintCallback(msg.sender).uniswapV3MintCallback(
        amount0,
        amount1
    );
    if (amount0 > 0 && balance0Before + amount0 > balance0())
        revert InsufficientInputAmount();
    if (amount1 > 0 && balance1Before + amount1 > balance1())
        revert InsufficientInputAmount();

    ...
}

function balance0() internal returns (uint256 balance) {
    balance = IERC20(token0).balanceOf(address(this));
}

function balance1() internal returns (uint256 balance) {
    balance = IERC20(token1).balanceOf(address(this));
}
```

首先，我们记录当前的代币余额。然后，我们在调用者上调用 `uniswapV3MintCallback` 方法——这是回调。可以预料的是，调用者（任何调用 `mint` 的人）是一个合约，因为非合约地址无法在 Ethereum 中实现函数。在这里使用回调，虽然对用户来说一点都不友好，但可以让合约使用其当前状态来计算代币数量——这是至关重要的，因为我们不能信任用户。

调用者应该实现 `uniswapV3MintCallback` 并在该函数中将代币转移到 Pool 合约。在调用回调函数之后，我们继续检查 Pool 合约的余额是否发生了变化：我们要求它们分别至少增加 `amount0` 和 `amount1` —— 这意味着调用者已经将代币转移到了 Pool。

最后，我们触发一个 `Mint` 事件：
```solidity
emit Mint(msg.sender, owner, lowerTick, upperTick, amount, amount0, amount1);
```

事件是合约数据在 Ethereum 中被索引以供稍后搜索的方式。每当合约的状态发生更改时，触发一个事件是一个很好的实践，以便让区块链浏览器知道何时发生了这种情况。事件还携带了有用的信息。在我们的例子中，它是调用者的地址、流动头寸所有者的地址、上限和下限 ticks、新的流动性和代币数量。此信息将存储为日志，其他任何人都可以收集所有合约事件并重现合约的活动，而无需遍历和分析所有区块和交易。

我们完成了！唷！现在，让我们测试 minting。

## 测试

在这一点上，我们不知道一切是否正常工作。在将我们的合约部署到任何地方之前，我们将编写一堆测试来确保合约正常工作。对我们来说幸运的是，Forge 是一个很棒的测试框架，它将使测试变得轻而易举。

创建一个新的测试文件：
```solidity
// test/UniswapV3Pool.t.sol
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.14;

import "forge-std/Test.sol";

contract UniswapV3PoolTest is Test {
    function setUp() public {}

    function testExample() public {
        assertTrue(true);
    }
}
```

让我们运行它：
```shell
$ forge test
Running 1 test for test/UniswapV3Pool.t.sol:UniswapV3PoolTest
[PASS] testExample() (gas: 279)
Test result: ok. 1 passed; 0 failed; finished in 5.07ms
```

它通过了！当然，它是！到目前为止，我们的测试只检查了 `true` 是否为 `true`！

测试合约只是继承自 `forge-std/Test.sol` 的合约。这个合约是一组测试实用程序，我们将逐步熟悉它们。如果你不想等待，请打开 `lib/forge-std/src/Test.sol` 并浏览一下。

测试合约遵循特定的约定：
1. `setUp` 函数用于设置测试用例。在每个测试用例中，我们都希望拥有一个配置好的环境，例如部署好的合约、mint 好的代币和初始化好的 Pools —— 我们将在 `setUp` 中完成所有这些操作。
2. 每个测试用例都以 `test` 前缀开头，例如 `testMint()`。这将使 Forge 能够区分测试用例和辅助函数（我们也可以拥有任何我们想要的函数）。

现在，让我们实际测试一下 minting。

### 测试代币

要测试 minting，我们需要代币。这不是问题，因为我们可以在测试中部署任何合约！此外，Forge 可以将开源合约安装为依赖项。具体来说，我们需要一个具有 minting 功能的 ERC20 合约。我们将使用来自 [Solmate](https://github.com/Rari-Capital/solmate) 的 ERC20 合约，Solmate 是一组经过 gas 优化的合约，并创建一个 ERC20 合约，该合约继承自 Solmate 合约并公开 minting（默认情况下是公开的）。

让我们安装 `solmate`：
```shell
$ forge install rari-capital/solmate
```

然后，让我们在 `test` 文件夹中创建 `ERC20Mintable.sol` 合约（我们只在测试中使用该合约）：
```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.14;

import "solmate/tokens/ERC20.sol";

contract ERC20Mintable is ERC20 {
    constructor(
        string memory _name,
        string memory _symbol,
        uint8 _decimals
    ) ERC20(_name, _symbol, _decimals) {}

    function mint(address to, uint256 amount) public {
        _mint(to, amount);
    }
}
```

我们的 `ERC20Mintable` 继承了 `solmate/tokens/ERC20.sol` 中的所有功能，并且我们还实现了公共的 `mint` 方法，该方法将允许我们 mint 任意数量的代币。

### Minting

现在，我们准备测试 minting。

首先，让我们部署所有必需的合约：
```solidity
// test/UniswapV3Pool.t.sol
...
import "./ERC20Mintable.sol";
import "../src/UniswapV3Pool.sol";

contract UniswapV3PoolTest is Test {
    ERC20Mintable token0;
    ERC20Mintable token1;
    UniswapV3Pool pool;

    function setUp() public {
        token0 = new ERC20Mintable("Ether", "ETH", 18);
        token1 = new ERC20Mintable("USDC", "USDC", 18);
    }

    ...
```
在 `setUp` 函数中，我们部署代币但不部署 Pools！这是因为我们所有的测试用例都将使用相同的代币，但它们中的每一个都将具有一个唯一的 Pool。

为了使 Pools 的设置更简洁、更简单，我们将在一个单独的函数 `setupTestCase` 中完成此操作，该函数接受一组测试用例参数。在我们的第一个测试用例中，我们将测试成功的流动性 minting。这就是测试用例参数的样子：
```solidity
function testMintSuccess() public {
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
```
1. 我们计划将 1 ETH 和 5000 USDC 存入 Pool。
2. 我们希望当前 tick 为 85176，下限 tick 和上限 tick 分别为 84222 和 86129（我们在上一章中计算出了这些值）。
3. 我们指定了预先计算的流动性和当前 $\sqrt{P}$。
4. 我们还希望存入流动性（`mintLiquidity` 参数）并在 Pool 合约请求时转移代币（`shouldTransferInCallback`）。我们不希望在每个测试用例中都这样做，所以我们想要这些标志。

接下来，我们使用上述参数调用 `setupTestCase`：
```solidity
function setupTestCase(TestCaseParams memory params)
    internal
    returns (uint256 poolBalance0, uint256 poolBalance1)
{
    token0.mint(address(this), params.wethBalance);
    token1.mint(address(this), params.usdcBalance);

    pool = new UniswapV3Pool(
        address(token0),
        address(token1),
        params.currentSqrtP,
        params.currentTick
    );

    if (params.mintLiqudity) {
        (poolBalance0, poolBalance1) = pool.mint(
            address(this),
            params.lowerTick,
            params.upperTick,
            params.liquidity
        );
    }

    shouldTransferInCallback = params.shouldTransferInCallback;
}
```
在这个函数中，我们 mint 代币并部署一个 Pool。此外，当设置了 `mintLiquidity` 标志时，我们在 Pool 中 mint 流动性。最后，我们设置 `shouldTransferInCallback` 标志，以便在 mint 回调中读取它：
```solidity
function uniswapV3MintCallback(uint256 amount0, uint256 amount1) public {
    if (shouldTransferInCallback) {
        token0.transfer(msg.sender, amount0);
        token1.transfer(msg.sender, amount1);
    }
}
```
是测试合约将提供流动性并将调用 Pool 上的 `mint` 函数，没有用户。测试合约将充当用户，因此它可以实现 mint 回调函数。

像这样设置测试用例不是强制性的，你可以用任何你觉得最舒服的方式来做。测试合约只是合约。

在 `testMintSuccess` 中，我们想要确保 Pool 合约：
1. 从我们这里获取正确的代币数量；
2. 创建一个具有正确键和流动性的 position；
3. 初始化我们指定的上下限 ticks；
4. 具有正确的 $\sqrt{P}$ 和 $L$。

让我们这样做。

Minting 发生在 `setupTestCase` 中，因此我们不需要再次这样做。该函数还返回了我们提供的数量，因此让我们检查它们：
```solidity
(uint256 poolBalance0, uint256 poolBalance1) = setupTestCase(params);

uint256 expectedAmount0 = 0.998976618347425280 ether;
uint256 expectedAmount1 = 5000 ether;
assertEq(
    poolBalance0,
    expectedAmount0,
    "incorrect token0 deposited amount"
);
assertEq(
    poolBalance1,
    expectedAmount1,
    "incorrect token1 deposited amount"
);
```
我们期望特定的预先计算的数量。我们还可以检查这些数量是否已转移到 Pool：
```solidity
assertEq(token0.balanceOf(address(pool)), expectedAmount0);
assertEq(token1.balanceOf(address(pool)), expectedAmount1);
```

接下来，我们需要检查 Pool 为我们创建的 position。记住 `positions` 映射中的键是一个哈希值吗？我们需要手动计算它，然后从合约中获取我们的 position：
```solidity
bytes32 positionKey = keccak256(
    abi.encodePacked(address(this), params.lowerTick, params.upperTick)
);
uint128 posLiquidity = pool.positions(positionKey);
assertEq(posLiquidity, params.liquidity);
```

> 由于 `Position.Info` 是一个 [struct](https://docs.soliditylang.org/en/latest/types.html#structs)，因此它在被获取时会被解构：每个字段都会被分配给一个单独的变量。

接下来是 ticks。同样，这很简单：
```solidity
(bool tickInitialized, uint128 tickLiquidity) = pool.ticks(
    params.lowerTick
);
assertTrue(tickInitialized);
assertEq(tickLiquidity, params.liquidity);

(tickInitialized, tickLiquidity) = pool.ticks(params.upperTick);
assertTrue(tickInitialized);
assertEq(tickLiquidity, params.liquidity);
```

最后，$\sqrt{P}$ 和 $L$：
```solidity
(uint160 sqrtPriceX96, int24 tick) = pool.slot0();
assertEq(
    sqrtPriceX96,
    5602277097478614198912276234240,
    "invalid current sqrtP"
);
assertEq(tick, 85176, "invalid current tick");
assertEq(
    pool.liquidity(),
    1517882343751509868544,
    "invalid current liquidity"
);
```

正如你所看到的，用 Solidity 编写测试并不难！

### 失败

当然，只测试成功的场景是不够的。我们还需要测试失败的情况。当提供流动性时，可能会出现什么问题？这里有一些提示：
1. 上限和下限 ticks 太大或太小。
2. 提供了零流动性。
3. 流动性提供者没有足够的代币。

我将把实现这些场景的任务留给你！请随时查看 [repo 中的代码](https://github.com/Jeiwan/uniswapv3-code/blob/milestone_1/test/UniswapV3Pool.t.sol)。
