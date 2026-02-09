# 用户界面

让我们使我们的 Web 应用程序更像一个真正的 DEX。我们现在可以移除硬编码的 swap 金额，并允许用户输入任意金额。此外，我们现在可以让用户在两个方向上进行 swap，因此我们还需要一个按钮来切换 token 输入。更新后，swap 表单将如下所示：

```jsx
<form className="SwapForm">
  <SwapInput
    amount={zeroForOne ? amount0 : amount1}
    disabled={!enabled || loading}
    readOnly={false}
    setAmount={setAmount_(zeroForOne ? setAmount0 : setAmount1, zeroForOne)}
    token={zeroForOne ? pair[0] : pair[1]} />
  <ChangeDirectionButton zeroForOne={zeroForOne} setZeroForOne={setZeroForOne} disabled={!enabled || loading} />
  <SwapInput
    amount={zeroForOne ? amount1 : amount0}
    disabled={!enabled || loading}
    readOnly={true}
    token={zeroForOne ? pair[1] : pair[0]} />
  <button className='swap' disabled={!enabled || loading} onClick={swap_}>Swap</button>
</form>
```

每个输入都分配了一个金额，具体取决于由 `zeroForOne` 状态变量控制的 swap 方向。较低的输入字段始终是只读的，因为它的值由 Quoter 合约计算。

`setAmount_` 函数执行两件事：它更新顶部输入的值，并调用 Quoter 合约来计算底部输入的值：

```js
const updateAmountOut = debounce((amount) => {
  if (amount === 0 || amount === "0") {
    return;
  }

  setLoading(true);

  quoter.callStatic
    .quote({ pool: config.poolAddress, amountIn: ethers.utils.parseEther(amount), zeroForOne: zeroForOne })
    .then(({ amountOut }) => {
      zeroForOne ? setAmount1(ethers.utils.formatEther(amountOut)) : setAmount0(ethers.utils.formatEther(amountOut));
      setLoading(false);
    })
    .catch((err) => {
      zeroForOne ? setAmount1(0) : setAmount0(0);
      setLoading(false);
      console.error(err);
    })
})

const setAmount_ = (setAmountFn) => {
  return (amount) => {
    amount = amount || 0;
    setAmountFn(amount);
    updateAmountOut(amount)
  }
}
```

请注意在 `quoter` 上调用的 `callStatic`——这就是我们在上一章中讨论的内容：我们需要强制 Ethers.js 进行静态调用。由于 `quote` 不是 `pure` 或 `view` 函数，Ethers.js 将尝试在交易中调用 `quote`。

就是这样！用户界面现在允许我们指定任意金额并在任一方向上进行 swap！
