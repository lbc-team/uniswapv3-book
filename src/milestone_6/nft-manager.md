# NFT ManagerContract

我们不会将 NFT 相关的功能添加到池合约中——我们需要一个单独的合约来合并 NFT 和流动性仓位。回想一下，在进行我们的实现时，我们构建了 `UniswapV3Manager` 合约，以方便与池合约的交互（使一些计算更简单并启用多池交换）。这个合约很好地展示了如何扩展核心 Uniswap 合约。我们将进一步推进这个想法。

我们需要一个 manager 合约，它将实现 ERC721 标准并管理流动性仓位。该合约将具有标准的 NFT 功能（铸造、销毁、转移、余额和所有权跟踪等），并将允许向池提供和移除流动性。该合约需要是池中流动性的实际所有者，因为我们不想让用户在没有铸造 Token 的情况下添加流动性，以及在没有销毁 Token 的情况下移除所有流动性。我们希望每个流动性仓位都与一个 NFT Token 相关联，并且我们希望它们同步。

让我们看看新合约中将有哪些函数：
1. 由于它将是一个 NFT 合约，它将拥有所有的 ERC721 函数，包括 `tokenURI`，它返回 NFT Token 图像的 URI；
1. `mint` 和 `burn` 用于同时铸造和销毁流动性和 NFT Token；
1. `addLiquidity` 和 `removeLiquidity` 用于在现有仓位中增加和移除流动性；
1. `collect`，用于在移除流动性后收集 Token。

好了，让我们开始编写代码。

## 最小合约

由于我们不想从头开始实现 ERC721 标准，我们将使用一个库。我们的依赖项中已经有了 [Solmate](https://github.com/transmissions11/solmate)，所以我们将使用 [它的 ERC721 实现](https://github.com/transmissions11/solmate/blob/main/src/tokens/ERC721.sol)。

> 使用 [来自 OpenZeppelin 的 ERC721 实现](https://github.com/OpenZeppelin/openzeppelin-contracts/tree/master/contracts/token/ERC721) 也是一个选择，但我更喜欢 Solmate 中 gas 优化的合约。

这将是 NFT manager 合约的最低要求：

```solidity
contract UniswapV3NFTManager is ERC721 {
    address public immutable factory;

    constructor(address factoryAddress)
        ERC721("UniswapV3 NFT Positions", "UNIV3")
    {
        factory = factoryAddress;
    }

    function tokenURI(uint256 tokenId)
        public
        view
        override
        returns (string memory)
    {
        return "";
    }
}
```

在实现 metadata 和 SVG 渲染器之前，`tokenURI` 将返回一个空字符串。我们添加了这个存根，以便 Solidity 编译器在处理合约的其余部分时不会失败（Solmate ERC721 合约中的 `tokenURI` 函数是 virtual 的，因此我们必须实现它）。

## 铸造

正如我们之前讨论的，铸造将涉及两个操作：向池中添加流动性和铸造 NFT。

为了保持池流动性仓位和 NFT 之间的链接，我们需要一个 mapping 和一个结构体：

```solidity
struct TokenPosition {
    address pool;
    int24 lowerTick;
    int24 upperTick;
}
mapping(uint256 => TokenPosition) public positions;
```

要找到一个仓位，我们需要：
1. 池地址；
1. 所有者地址；
1. 仓位的边界（lower 和 upper ticks）。

由于 NFT manager 合约将是通过它创建的所有仓位的所有者，我们不需要存储仓位的所有者地址，我们只能存储其余数据。`positions` mapping 中的键是 Token ID；该映射将 NFT ID 链接到查找流动性仓位所需的位置数据。

让我们来实现铸造：

```solidity
struct MintParams {
    address recipient;
    address tokenA;
    address tokenB;
    uint24 fee;
    int24 lowerTick;
    int24 upperTick;
    uint256 amount0Desired;
    uint256 amount1Desired;
    uint256 amount0Min;
    uint256 amount1Min;
}

function mint(MintParams calldata params) public returns (uint256 tokenId) {
    ...
}
```

铸造参数与 `UniswapV3Manager` 的参数相同，但增加了 `recipient`，它允许将 NFT 铸造到另一个地址。

在 `mint` 函数中，我们首先向池中添加流动性：

```solidity
IUniswapV3Pool pool = getPool(params.tokenA, params.tokenB, params.fee);

(uint128 liquidity, uint256 amount0, uint256 amount1) = _addLiquidity(
    AddLiquidityInternalParams({
        pool: pool,
        lowerTick: params.lowerTick,
        upperTick: params.upperTick,
        amount0Desired: params.amount0Desired,
        amount1Desired: params.amount1Desired,
        amount0Min: params.amount0Min,
        amount1Min: params.amount1Min
    })
);
```

`_addLiquidity` 与 `UniswapV3Manager` 合约中的 `mint` 函数体相同：它将 ticks 转换为 $\sqrt(P)$，计算流动性量，并调用 `pool.mint()`。

接下来，我们铸造一个 NFT：

```solidity
tokenId = nextTokenId++;
_mint(params.recipient, tokenId);
totalSupply++;
```

`tokenId` 设置为当前的 `nextTokenId`，然后递增后者。`_mint` 函数由 Solmate 的 ERC721 合约提供。在铸造新的 Token 之后，我们更新 `totalSupply`。

最后，我们需要存储有关新 Token 和新仓位的信息：

```solidity
TokenPosition memory tokenPosition = TokenPosition({
    pool: address(pool),
    lowerTick: params.lowerTick,
    upperTick: params.upperTick
});

positions[tokenId] = tokenPosition;
```

这将稍后帮助我们通过 Token ID 找到流动性仓位。

## 增加流动性

接下来，我们将实现一个函数，以将流动性添加到现有仓位，以防我们想要在已经有流动性的仓位中添加更多流动性。在这种情况下，我们不想铸造 NFT，而只想增加现有仓位中的流动性量。为此，我们只需要提供 Token ID 和 Token 数量：

```solidity
function addLiquidity(AddLiquidityParams calldata params)
    public
    returns (
        uint128 liquidity,
        uint256 amount0,
        uint256 amount1
    )
{
    TokenPosition memory tokenPosition = positions[params.tokenId];
    if (tokenPosition.pool == address(0x00)) revert WrongToken();

    (liquidity, amount0, amount1) = _addLiquidity(
        AddLiquidityInternalParams({
            pool: IUniswapV3Pool(tokenPosition.pool),
            lowerTick: tokenPosition.lowerTick,
            upperTick: tokenPosition.upperTick,
            amount0Desired: params.amount0Desired,
            amount1Desired: params.amount1Desired,
            amount0Min: params.amount0Min,
            amount1Min: params.amount1Min
        })
    );
}
```

此函数确保存在现有 Token，并使用现有仓位的参数调用 `pool.mint()`。

## 移除流动性

回想一下，在 `UniswapV3Manager` 合约中，我们没有实现 `burn` 函数，因为我们希望用户成为流动性仓位的所有者。现在，我们希望 NFT manager 成为所有者。我们可以实现流动性销毁：

```solidity
struct RemoveLiquidityParams {
    uint256 tokenId;
    uint128 liquidity;
}

function removeLiquidity(RemoveLiquidityParams memory params)
    public
    isApprovedOrOwner(params.tokenId)
    returns (uint256 amount0, uint256 amount1)
{
    TokenPosition memory tokenPosition = positions[params.tokenId];
    if (tokenPosition.pool == address(0x00)) revert WrongToken();

    IUniswapV3Pool pool = IUniswapV3Pool(tokenPosition.pool);

    (uint128 availableLiquidity, , , , ) = pool.positions(
        poolPositionKey(tokenPosition)
    );
    if (params.liquidity > availableLiquidity) revert NotEnoughLiquidity();

    (amount0, amount1) = pool.burn(
        tokenPosition.lowerTick,
        tokenPosition.upperTick,
        params.liquidity
    );
}
```

我们再次检查提供的 Token ID 是否有效。我们还需要确保仓位有足够的流动性来销毁。

## 收集 Token

NFT manager 合约还可以在销毁流动性后收集 Token。请注意，收集到的 Token 将发送到 `msg.sender`，因为该合约代表调用者管理流动性：

```solidity
struct CollectParams {
    uint256 tokenId;
    uint128 amount0;
    uint128 amount1;
}

function collect(CollectParams memory params)
    public
    isApprovedOrOwner(params.tokenId)
    returns (uint128 amount0, uint128 amount1)
{
    TokenPosition memory tokenPosition = positions[params.tokenId];
    if (tokenPosition.pool == address(0x00)) revert WrongToken();

    IUniswapV3Pool pool = IUniswapV3Pool(tokenPosition.pool);

    (amount0, amount1) = pool.collect(
        msg.sender,
        tokenPosition.lowerTick,
        tokenPosition.upperTick,
        params.amount0,
        params.amount1
    );
}
```

## 销毁

最后，销毁。与合约的其他函数不同，此函数不处理池：它仅销毁 NFT。要销毁 NFT，基础仓位必须为空，并且必须收集 Token。因此，如果我们想销毁 NFT，我们需要：
1. 调用 `removeLiquidity` 并移除整个仓位流动性；
1. 调用 `collect` 以在销毁仓位后收集 Token；
1. 调用 `burn` 以销毁 Token。

```solidity
function burn(uint256 tokenId) public isApprovedOrOwner(tokenId) {
    TokenPosition memory tokenPosition = positions[tokenId];
    if (tokenPosition.pool == address(0x00)) revert WrongToken();

    IUniswapV3Pool pool = IUniswapV3Pool(tokenPosition.pool);
    (uint128 liquidity, , , uint128 tokensOwed0, uint128 tokensOwed1) = pool
        .positions(poolPositionKey(tokenPosition));

    if (liquidity > 0 || tokensOwed0 > 0 || tokensOwed1 > 0)
        revert PositionNotCleared();

    delete positions[tokenId];
    _burn(tokenId);
    totalSupply--;
}
```

就这样！
