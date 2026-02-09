# 输出数量计算

我们的 Uniswap 数学公式集合还缺少最后一部分：在出售 ETH（即：出售 token $x$）时计算输出数量的公式。在前一个里程碑中，我们有一个类似的公式用于购买 ETH 的情况（购买 token $x$）：

$$\Delta \sqrt{P} = \frac{\Delta y}{L}$$

此公式找到出售 token $y$ 时的价格变化。然后，我们将此变化添加到当前价格以找到目标价格：

$$\sqrt{P_{target}} = \sqrt{P_{current}} + \Delta \sqrt{P}$$

现在，我们需要一个类似的公式来找到出售 token $x$（在本例中为 ETH）和购买 token $y$（在本例中为 USDC）时的目标价格。

回想一下，token $x$ 的变化可以计算为：

$$\Delta x = \Delta \frac{1}{\sqrt{P}}L$$

从此公式中，我们可以找到目标价格：

$$\Delta x = (\frac{1}{\sqrt{P_{target}}} - \frac{1}{\sqrt{P_{current}}}) L$$
$$= \frac{L}{\sqrt{P_{target}}} - \frac{L}{\sqrt{P_{current}}}$$

由此，我们可以使用基本的代数变换找到 $\sqrt{P_{target}}$：

$$\sqrt{P_{target}} = \frac{\sqrt{P}L}{\Delta x \sqrt{P} + L}$$

知道目标价格后，我们可以像在前一个里程碑中找到输出量一样找到输出量。

让我们用新公式更新我们的 Python 脚本：
```python
# Swap ETH for USDC
amount_in = 0.01337 * eth

print(f"\nSelling {amount_in/eth} ETH")

price_next = int((liq * q96 * sqrtp_cur) // (liq * q96 + amount_in * sqrtp_cur))

print("New price:", (price_next / q96) ** 2)
print("New sqrtP:", price_next)
print("New tick:", price_to_tick((price_next / q96) ** 2))

amount_in = calc_amount0(liq, price_next, sqrtp_cur)
amount_out = calc_amount1(liq, price_next, sqrtp_cur)

print("ETH in:", amount_in / eth)
print("USDC out:", amount_out / eth)
```

它的输出：
```shell
Selling 0.01337 ETH
New price: 4993.777388290041
New sqrtP: 5598789932670289186088059666432
New tick: 85163
ETH in: 0.013369999999998142
USDC out: 66.80838889019013
```

这意味着当我们使用在上一步中提供的流动性出售 0.01337 ETH 时，我们将获得 66.8 USDC。

这看起来不错，但 Python 就到此为止！我们将用 Solidity 实现所有的数学计算。
