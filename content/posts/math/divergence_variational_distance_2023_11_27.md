---
title: 信息论 (二)
subtitle: Divergence and variational distance
date: 2023-11-27
slug: Divergence_Variational_Distance_2023_11_27
category: Math
series: Information Theory
summary: Follow-up notes on divergence, cross-entropy, mutual information, and variational distance.
cover_image: images/blog/category_cover/math.jpg
tags:
  - Math
  - Information Theory
  - Divergence
toc: true
output_path: blog/math/information_theory/Divergence_Variational_Distance_2023_11_27.html
---

# ※  Divergence

## 1  散度的定义

给定两个定义在同一字母表$\mathcal{X}$上的随机变量$X和\hat{X}$，定义散度(又称为*Kullback-Leibler divergence*)：

$$
D_{KL}(X||\hat{X}) = D_{KL}(P_{X}||P_{\hat{X}}):= E_{X}[log_{2}\frac{P_{X}(X)}{P_{\hat{X}}(X)}] = \sum _{x\in \mathcal{X}}P_{X}(x)log_{2}\frac{P_{X}(x)}{P_{\hat{X}}(x)} \tag{1-1}
$$

换句话说，散度就是分布$P_X$相比$P_\hat{X}$的对数似然比值的期望。说人话可以这样理解：

> It is the amount of information lost when Q is used to approximate P

> It is the expected number of extra [bits](https://en.wikipedia.org/wiki/Bit) required to [code](https://en.wikipedia.org/wiki/Huffman_coding) samples from *P* using a code optimized for *Q* rather than the code optimized for *P*

## 2  散度的动机

如果使用一个错误的分布来近似真实分布，那么事实上每一个元事件需要多额外的信息量的期望是多少？

很显然，期望是概率加权的均值，这个概率是事件真实概率，而额外的信息量怎么表示？可以用自信息的差，也就是：

$$
-log_{2}P_{\hat{X}}(x)-(-log_{2}P_{X}(x)) = log_{2}\frac{P_{X}(x)}{P_{\hat{X}}(x)}
$$

这就类似于计算一个编码系统，当它采用有偏差的分布来设计最优编码方案时，它在实际应用中实际每个编码字母平均付出的额外代价。

### 2.1  交叉熵

注意到散度公式可以写为如下形式：

$$
\begin{aligned} D_{KL}(X||\hat{X}) & = \sum _{x\in \mathcal{X}}P_{X}(x)\cdot log_{2}\frac{1}{P_{\hat{X}}(x)}-\sum _{x\in \mathcal{X}}-P_{X}(x)\cdot log_{2}P_{X}(x) \\ \text{(2-1)} & & = CH(X,\hat{X})-H(X) \end{aligned}
$$

其中，我们将$CH(\cdot )$定义为交叉熵(Cross Entrophy)，表示使用一个估计分布$P_{\hat{X}}$来设计编码方案时候，平均需要的信息量。很显然交叉熵非负。当估计分布等于真实分布时候，交叉熵就是熵。即$CH(X,X)=H(X)$。

## 3  散度的属性

### 3.1  非负性 Nonnegativity of divergence

$$
D_{KL}(X||\hat{X})\ge 0 \tag{3-1}
$$

等式当且仅当对于$\forall x \in \mathcal{X}, P_X(x)=P_{\hat{X}}(x)$。

Proof：

$$
\begin{aligned} D_{KL}(X||\hat{X}) & = D_{KL}(P_{X}||P_{\hat{X}}) = \sum _{x\in \mathcal{X}}P_{X}(x)log_{2}\frac{P_{X}(x)}{P_{\hat{X}}(x)} \\ & \ge (\sum _{x\in \mathcal{X}}P_{X}(x))log_{2}\frac{\sum _{a\in \mathcal{X}}P_{X}(a)}{\sum _{b\in \mathcal{X}}P_{\hat{X}}(b)} \\ & = 0 \end{aligned}
$$

根据log-sum不等式，上述不等式成立，且等号当且仅当对于$\forall x \in \mathcal{X}, P_X(x)=P_{\hat{X}}(x)$。

### 3.2  互信息与散度的关联 Mutual inforamtion and divergence

$$
I(X; Y) = D(P_{X,Y}||P_{X}\times P_{Y}) \tag{3-2}
$$

根据定义容易得证。

### 3.3  Refinement cannot decrease divergence

设$P_X$和$P_{\hat{X}}$分别是$P_U$和$P_{\hat{U}}$的细化，那么：

$$
D_{KL}(P_{X}||P_{\hat{X}})\ge D_{KL}(P_{U}||P_{\hat{U}}) \tag{3-3}
$$

### 3.4  散度的缺陷

使用散度作为衡量两个分步之间的测度有一个缺陷，就是散度不具有对称性，同时它也不满足三角不等式，所以更不能作为真正的距离(distance)或指标(metric)。

什么是真正的距离或者指标呢？它是一个满足一下条件的函数。

给定一个非空集合A，函数$d : A\times A \rightarrow [0,\infin)$ 如果满足以下三个性质，则可以称之为距离或者指标。

1. **非负性：**$\forall a,b \in A, d(a,b) \ge 0$成立，并且等号当且仅当a=b时成立。
2. **对称性：**$\forall a,b \in A, d(a,b) = d(b,a)$。
3. **三角不等性：**$\forall a,b,c \in A, d(a,b) + d(b,c) \ge d(a,c)$。

# ※  Variational distance ($\mathcal{L_1}$-distance)

## 1  变分距离的定义

散度不是真正的距离，由此引出变分距离。对于具有相同字母表$\mathcal{X}$的两个分布$P_X$和$P_{\hat{X}}$，变分距离定义为：

$$
||P_{X}-P_{\hat{X}}||:= \sum _{x\in \mathcal{X}}|P_{X}(x)-P_{\hat{X}}(x)|
$$

## 2  变分距离的引论

$$
||P_{X}-P_{\hat{X}}|| = 2\cdot sup_{E\subset \mathcal{X}}|P_{X}(E)-P_{\hat{X}}(E)| = 2\cdot \sum _{x\in \mathcal{X};P_{X}(x)>P_{\hat{X}}(x)}(P_{X}(x)-P_{\hat{X}}(x))
$$

其中符号$\sup$表示集合的最小上界。

Proof:

1. 先证第二个等号右侧等于第一个等号左侧。

设集合$\mathcal{A} := {x \in \mathcal{X}:P_X(x) > P_{\hat{X}}(x)}$，且$\mathcal{A}^c$为其补集，显然有：

$$
1 = P_{X}(\mathcal{A})+P_{X}(\mathcal{A}^{c}) = P_{\hat{X}}(\mathcal{A})+P_{\hat{X}}(\mathcal{A}^{c})⇒P_{\hat{X}}(\mathcal{A}^{c})-P_{X}(\mathcal{A}^{c}) = P_{X}(\mathcal{A})-P_{\hat{X}}(\mathcal{A})
$$

所以，

$$
\begin{aligned} ||P_{X}-P_{\hat{X}}|| & = \sum _{x\in \mathcal{X}}|P_{X}(x)-P_{\hat{X}}(x)| \\ & = \sum _{x\in \mathcal{A}}|P_{X}(x)-P_{\hat{X}}(x)|+\sum _{x\in \mathcal{A}^{c}}|P_{X}(x)-P_{\hat{X}}(x)| \\ & = \sum _{x\in \mathcal{A}}(P_{X}(x)-P_{\hat{X}}(x))+\sum _{x\in \mathcal{A}^{c}}(P_{\hat{X}}(x)-P_{X}(x)) \\ & = \sum _{x\in \mathcal{A}}(P_{X}(x)-P_{\hat{X}}(x))+P_{\hat{X}}(\mathcal{A}^{c})-P_{X}(\mathcal{A}^{c}) \\ & = \sum _{x\in \mathcal{A}}(P_{X}(x)-P_{\hat{X}}(x))+P_{X}(\mathcal{A})-P_{\hat{X}}(\mathcal{A}) \\ & = \sum _{x\in \mathcal{A}}(P_{X}(x)-P_{\hat{X}}(x))+\sum _{x\in \mathcal{A}}(P_{X}(x)-P_{\hat{X}}(x)) \\ & = 2\cdot \sum _{x\in \mathcal{A}}(P_{X}(x)-P_{\hat{X}}(x)) \end{aligned}
$$

1. 再证明第一个等号两侧相等

对于任意集合$E \subset \mathcal{X}$，根据绝对值不等式易得：

$$
\begin{aligned} ||P_{X}-P_{\hat{X}}|| & = \sum _{x\in \mathcal{X}}|P_{X}(x)-P_{\hat{X}}(x)| \\ & = \sum _{x\in E}|P_{X}(x)-P_{\hat{X}}(x)|+\sum _{x\in E^{c}}|P_{X}(x)-P_{\hat{X}}(x)| \\ & \ge |\sum _{x\in E}[P_{X}(x)-P_{\hat{X}}(x)]|+|\sum _{x\in E^{c}}[P_{X}(x)-P_{\hat{X}}(x)]| \\ & = |P_{X}(E)-P_{\hat{X}}(E)|+|P_{X}(E^{c})-P_{\hat{X}}(E^{c})| \\ & = |P_{X}(E)-P_{\hat{X}}(E)|+|P_{X}(E)-P_{\hat{X}}(E)| \\ & = 2\cdot |P_{X}(E)-P_{\hat{X}}(E)| \end{aligned}
$$

所以，$||P_X-P_{\hat{X}}|| \ge 2\cdot \sup_{E \subset \mathcal{X}}| P_X(E)-P_{\hat{X}}(E) |$。

根据最小上界定义易得

$$
\begin{aligned} 2\cdot sup_{E\subset \mathcal{X}}|P_{X}(E)-P_{\hat{X}}(E)| & \ge 2\cdot |P_{X}(\mathcal{A})-P_{\hat{X}}(\mathcal{A})| \\ & = |P_{X}(\mathcal{A})-P_{\hat{X}}(\mathcal{A})|+|P_{\hat{X}}(\mathcal{A}^{c})-P_{X}(\mathcal{A}^{c})| \\ & = |\sum _{x\in \mathcal{A}}[P_{X}(x)-P_{\hat{X}}(x)]|+|\sum _{x\in \mathcal{A}^{c}}[P_{X}(x)-P_{\hat{X}}(x)]| \\ & = \sum _{x\in \mathcal{A}}|P_{X}(x)-P_{\hat{X}}(x)|+\sum _{x\in \mathcal{A}^{c}}|P_{X}(x)-P_{\hat{X}}(x)| \\ & = ||P_{X}-P_{\hat{X}}|| \end{aligned}
$$

所以第一个等号只能相等得证。

综合1、2推理得证。

# ※  Divergence VS Variational distance

## 1  Pinsker's inequality

$$
D_{KL}(X||\hat{X})\ge \frac{log_{2}(e)}{2}\cdot ||P_{X}-P_{\hat{X}}||^{2}
$$

## 2  Upper bound of divergence

$$
D_{KL}(X||\hat{X})\le \frac{log_{2}(e)}{\min _{{x:P_{X}(x)>0}}\min {P_{X}(x),P_{\hat{X}}(x)}}\cdot ||P_{X}-P_{\hat{X}}||
$$
