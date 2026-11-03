---
title: Behavior Cloning 与 PLID
date: 2026-10-20
summary: 说明 Behavior Cloning 的状态分布偏移，并推导 PLID / DAgger 如何用交互式专家标签修正策略。
draft: false
---

Behavior Cloning 把专家示范当作监督学习数据，但模型部署后会访问训练时没有覆盖的状态。本文从模仿学习的基本形式化出发，说明 covariate shift 与 compounding errors，并推导 PLID / DAgger 如何通过当前策略 rollout、再由专家补充标签，逐步修正状态分布偏移。

前置知识：概率、条件概率、监督学习损失，以及基本的 Markov Decision Process（MDP）概念。KL 散度的定义见 [Active Learning](/blog/active-learning/#section-5)。

> 模仿学习为什么需要交互式纠错

## 1. 问题设定

假设我们要训练一个机器人完成导航任务。专家已经执行了许多次任务，我们记录下它在每个状态下采取的动作。最直接的做法是把这些记录当作监督学习数据：输入状态，预测专家动作。

这种方法叫做 **Behavior Cloning（行为克隆，BC）**。它的直觉很简单：模型不需要自己发现策略，只需要学习专家已经展示过的行为。

问题在于，模型真正执行任务时，并不会永远停留在专家访问过的状态上。只要模型在某一步出现一个小误差，它就可能进入训练数据中很少出现、甚至从未出现过的状态。

> 模仿学习的困难不只是预测正确动作，而是策略会通过自己的动作改变未来访问的状态分布。

## 2. 形式化

我们用一个 MDP（Markov Decision Process，马尔可夫决策过程）描述环境。设：

- $\mathcal S$：状态空间；
- $\mathcal A$：动作空间；
- $s_t\in\mathcal S$：时间 $t$ 的状态；
- $a_t\in\mathcal A$：时间 $t$ 的动作；
- $P(s_{t+1}\mid s_t,a_t)$：环境转移概率。

专家策略记为：

$$
\pi_E(a\mid s)
$$

它表示专家在状态 $s$ 下选择动作 $a$ 的条件概率。待学习策略记为：

$$
\pi_\theta(a\mid s)
$$

其中 $\theta$ 是模型参数。

所有示范组成数据集：

$$
\mathcal D_E
=
\left\{
(s_n,a_n)
\right\}_{n=1}^{N}
$$

这里还要区分策略和状态访问分布。策略 $\pi(a\mid s)$ 描述给定状态下如何选择动作；$d_\pi^t(s)$ 表示执行策略 $\pi$ 后，在第 $t$ 步处于状态 $s$ 的概率。策略决定动作，动作又影响环境转移，因此策略也会间接决定未来访问哪些状态。

## 3. Behavior Cloning

### 3.1 训练目标

如果动作是离散的，可以使用最大似然或交叉熵损失：

$$
\mathcal L_{\mathrm{BC}}(\theta)
=
-\frac{1}{N}
\sum_{n=1}^{N}
\log \pi_\theta(a_n\mid s_n)
$$

如果动作是连续值，也可以使用均方误差：

$$
\mathcal L_{\mathrm{BC}}(\theta)
=
\frac{1}{N}
\sum_{n=1}^{N}
\left\|
\hat a_\theta(s_n)-a_n
\right\|_2^2
$$

两种损失表达的是同一个基本思想：在示范数据中的状态下，模型应该采取与专家相同或相近的动作。

### 3.2 状态分布

专家示范主要来自专家策略访问过的状态，因此 BC 实际优化的是：

$$
\mathbb E_{s\sim d_{\pi_E}}
\left[
\ell\bigl(\pi_\theta(s),\pi_E(s)\bigr)
\right]
$$

BC 并不是在所有可能状态上学习专家策略，而是在专家访问过的状态分布上拟合专家动作。

## 4. 误差累积

### 4.1 状态偏移

专家执行任务时，状态来自 $s_t\sim d_{\pi_E}^t$；模型执行任务时，状态来自 $s_t\sim d_{\pi_\theta}^t$。一般来说：

$$
d_{\pi_E}^t\neq d_{\pi_\theta}^t
$$

训练时模型看到的是专家状态，部署时模型却会根据自己的动作进入新的状态。这就是 **covariate shift（协变量偏移）** 在序列决策中的表现。

### 4.2 状态递推

状态分布的递推关系为：

$$
d_\pi^{t+1}(s')
=
\sum_{s\in\mathcal S}
 d_\pi^t(s)
\sum_{a\in\mathcal A}
 \pi(a\mid s)P(s'\mid s,a)
$$

右侧三项分别表示当前状态概率、动作概率和环境转移概率。改变策略不仅会改变当前动作，还会改变之后所有时间步的状态分布。

### 4.3 误差连锁

一次小动作误差可能使模型进入示范数据很少覆盖的状态；在新状态下，模型的预测更不可靠；新的错误又使它进一步偏离专家轨迹。这就是 **compounding errors（误差累积）**。

因此，较低的单步验证误差并不必然意味着较高的任务成功率。

## 5. PLID

### 5.1 核心直觉

PLID 的全称是 **Policy Learning via an Interactive Demonstrator**。它与经典 DAgger 的核心思想一致：不只学习专家走过的正确轨迹，还要让当前策略自己运行；当它进入偏离状态时，请专家告诉它在这些状态下应该采取什么动作。

训练过程如下：

1. 使用专家示范训练初始策略 $\pi_0$；
2. 让 $\pi_0$ 自己与环境交互；
3. 收集模型实际访问的状态；
4. 对这些状态询问专家动作；
5. 将新数据加入原始示范数据；
6. 重新训练策略并重复上述过程。

### 5.2 交互标注

第 $m$ 轮中，模型负责产生状态：

$$
s\sim d_{\pi_m}
$$

专家负责提供动作标签：

$$
a\sim \pi_E(\cdot\mid s)
$$

于是得到新数据集：

$$
\mathcal D_m
=
\left\{
(s_{m,n},a_{m,n})
\right\}_{n=1}^{N}
$$

这里的关键不是让模型模仿自己的动作，而是让模型探索自己会访问的状态，再让专家在这些状态上提供正确标签。

### 5.3 数据聚合

PLID / DAgger 通常保留旧数据：

$$
\mathcal D_{0:m}
=
\bigcup_{i=0}^{m}\mathcal D_i
$$

然后在聚合数据上重新训练：

$$
\theta_{m+1}
=
\arg\min_\theta
\sum_{(s,a)\in\mathcal D_{0:m}}
-
\log\pi_\theta(a\mid s)
$$

保留旧数据的作用是让模型同时学习专家正常执行时访问的状态，以及模型偏离后需要恢复的状态。

## 6. 数学目标

在第 $m$ 轮，理想目标是在模型实际访问的状态上，让学习策略接近专家策略：

$$
\hat\theta_{m+1}
=
\arg\min_\theta
\mathbb E_{s\sim d_{\pi_m}}
\left[
D_{\mathrm{KL}}
\left(
\pi_E(\cdot\mid s)
\|\pi_\theta(\cdot\mid s)
\right)
\right]
$$

根据 [KL 散度](/blog/active-learning/#section-5) 的定义：

$$
D_{\mathrm{KL}}(p\|q)
=
\mathbb E_{x\sim p}
\left[
\log\frac{p(x)}{q(x)}
\right]
$$

代入两个策略：

$$
\begin{aligned}
&D_{\mathrm{KL}}
\left(
\pi_E(\cdot\mid s)
\|\pi_\theta(\cdot\mid s)
\right)\\
&=
\mathbb E_{a\sim\pi_E(\cdot\mid s)}
\left[
\log\pi_E(a\mid s)
-
\log\pi_\theta(a\mid s)
\right]
\end{aligned}
$$

第一项只依赖固定的专家策略，与 $\theta$ 无关。因此，最小化 KL 等价于最大化：

$$
\mathbb E_{\substack{s\sim d_{\pi_m}\\a\sim\pi_E(\cdot\mid s)}}
\left[
\log\pi_\theta(a\mid s)
\right]
$$

换成最小化形式，就是：

$$
-\mathbb E_{\substack{s\sim d_{\pi_m}\\a\sim\pi_E(\cdot\mid s)}}
\left[
\log\pi_\theta(a\mid s)
\right]
$$

这仍然是 BC 的负对数似然损失。真正发生变化的是期望所在的状态分布：

- BC：主要在 $s\sim d_{\pi_E}$ 上学习；
- PLID：不断加入 $s\sim d_{\pi_m}$ 的模型访问状态。

因此可以把 PLID 概括为：

> 不改变“如何拟合专家动作”的基本损失，而是改变“在哪些状态上获得专家标签”。

## 7. 训练流程

一个更接近工程实践的训练闭环是：

```
专家示范
   ↓
数据清洗与时间对齐
   ↓
初始化 Behavior Cloning
   ↓
当前策略 rollout
   ↓
记录失败状态与恢复状态
   ↓
专家接管或提供 correction
   ↓
数据聚合与重新训练
   ↓
离线评估 + 在线 rollout
```

理论中的“询问专家”在真实系统中可能对应：

- 人类实时接管；
- 对失败片段进行离线标注；
- 规则系统提供动作 correction；
- 更强模型生成辅助标签；
- 从日志中筛选高风险状态。

## 8. 适用条件

### 8.1 专家反馈成本

PLID 需要专家为模型新访问的状态提供标签。如果模型经常进入危险或复杂状态，标注成本可能很高。

### 8.2 偏离状态

专家不仅要能展示正常轨迹，还要能回答：模型已经犯错后，现在应该如何恢复。如果专家只提供理想轨迹，PLID 的优势会受到限制。

### 8.3 状态信息

如果当前观测无法判断正确动作，问题可能不是数据覆盖不足，而是部分可观测性、历史信息缺失或状态表示不充分。

### 8.4 评估指标

动作预测准确率只衡量单步模仿误差。实际部署还需要评估：

- 任务成功率；
- 长时间 rollout 稳定性；
- 偏离后的恢复能力；
- 高风险状态下的安全性；
- 专家接管率与数据回流效率。

## 9. 总结

Behavior Cloning 把专家示范转化为监督学习问题，但它默认训练数据覆盖了模型执行时会遇到的状态。这个假设在序列决策中通常不成立。

模型的一次小动作误差可能改变未来状态分布，并造成连续的误差累积。PLID / DAgger 的解决方案是让当前策略自己探索，再由专家在模型实际访问的状态上补充动作标签，最后通过数据聚合重新训练策略。

从数学上看，PLID 仍然使用类似 BC 的动作损失，但把训练状态分布从专家访问分布扩展到了模型访问分布：

$$
\text{BC：}\quad s\sim d_{\pi_E}
$$

$$
\text{PLID：}\quad s\sim d_{\pi_m}
$$

这也是从 Behavior Cloning 走向 Distribution Matching 的起点：当专家持续标注成本过高时，下一步是不再逐个纠正动作，而是直接让模型产生与专家相似的行为分布。下一篇笔记讨论 [Distribution Matching 与 GAIL](/blog/distribution-matching-gail/)。

## 参考资料

- [课程讲义](https://github.com/enalisnick/enalisnick.github.io/blob/master/ML_with_Humans_Course_Notes.pdf)
- 系列：[Imitation Learning](/series/imitation-learning/)
- 系列下一篇：[Distribution Matching 与 GAIL](/blog/distribution-matching-gail/)

