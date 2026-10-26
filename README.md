# xiaofu2730.github.io

个人静态博客与学术笔记网站，基于 GitHub Pages 托管。现已全面支持**纯 Markdown 写作原生渲染工作流**。

---

## 博客写作工作流 (Blog Authoring Workflow)

### 🌟 交互式创作与发布助手 (XiaoFu Blog Studio)

针对 macOS 提供了优雅简洁的**交互式可视化创作控制台**，契合博客一贯的高级简约审美风格。

#### 启动方式：
1. **Finder 双击启动（推荐）**：在 macOS Finder 中直接双击项目根目录下的 **`BlogAssistant.command`**，将自动拉起服务并在默认浏览器打开助手窗口。
2. **终端启动**：
   ```bash
   python3 scripts/blog_assistant.py
   ```
   默认访问地址：`http://localhost:5000/studio`

#### 助手三大核心功能：
- 📝 **新建文章**：图形化填写标题、副标题、分类（自动补全已有分类）、系列专栏、标签胶囊、文章摘要，可视化选择分类封面图（Cover Picker），点击“创建并打开”后会自动生成标准 Front Matter 及配套同级配图目录（`<slug>.assets/`），并使用 Mac 默认 Markdown 编辑器（如 Typora）自动打开。
- 📥 **批量导入与格式化**：将一个或多个已有 Markdown 文档直接**拖入窗口**，系统将自动分析文档标题、字符数、公式特征，自动清洗 LaTeX 公式符号并规范化同级配图路径，一键迁移归档至博客目录。
- 📚 **文章管理与发布**：全景浏览全站文章字数、分类、生成状态。支持“一键编译整站”、“在默认编辑器中修改”以及“在浏览器中一键预览 HTML”。

---

### 命令行工作流 (CLI Workflow)

### 1. 环境准备 (一键安装)

本生成器基于 Python 3 编写，推荐使用本地虚拟环境：

```bash
# 创建虚拟环境并安装依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **提示**：若未手动激活虚拟环境，直接运行 `python3 scripts/generate_blog.py` 也会自动检测并使用项目根目录下的 `.venv`。

---

### 2. 新建文章 (CLI 脚手架)

使用命令行一键创建新文章及同名配图资源文件夹：

```bash
# 语法: python3 scripts/generate_blog.py --new "<文章标题>" -c "<分类>" [-s "<系列名>"] [-t "<标签1,标签2>"]
python3 scripts/generate_blog.py --new "强化学习入门" -c "ML" -s "Reinforcement Learning" -t "ML,RL"
```

该命令会自动创建：
- `content/posts/ml/qiang_hua_xue_xi_ru_men.md`（预置标准 Front Matter 和示例排版）
- `content/posts/ml/qiang_hua_xue_xi_ru_men.assets/`（用于存放该文章配图的同级目录）

---

### 3. Markdown 特性支持

#### YAML Front Matter 元数据规范
```yaml
---
title: 文章标题
subtitle: 可选副标题
date: 2026-10-25
slug: post_slug
category: ML
series: Reinforcement Learning # 可选
summary: 文章在 blog.html 列表页展示的一句话摘要
cover_image: images/blog/category_cover/ai.jpg
tags:
  - ML
  - Reinforcement Learning
toc: true                      # 是否生成本页目录 (默认: true)
---
```

#### 数学公式 (KaTeX 极速渲染)
- **行内公式**：使用 `$ ... $`，例如 `$\nabla_\theta J(\theta)$`。
- **块级公式**：使用 `$$ ... $$`，例如：
  $$
  \mathcal{L}(\theta) = \mathbb{E}_{x \sim p(x)} \left[ \log p_\theta(x) \right]
  $$

#### 本地配图存放 (同级目录模式)
只需将配图存放在与文章同级的 `<slug>.assets/` 目录下，在 Markdown 中使用标准相对路径引用：
```markdown
![算法流程示意图](qiang_hua_xue_xi_ru_men.assets/flowchart.png)
```
编译脚本会在构建时自动同步资源目录到生成的 HTML 目录中，所见即所得。

#### 代码高亮与一键复制
编写标准带语言标识的代码块：
````markdown
```python
def train_agent():
    print("Training started...")
```
````
前端会自动展示语言标识徽章并支持一键“Copy”复制代码。

#### GitHub 风格提示块 (Callouts)
```markdown
> [!NOTE]
> 这是一个常规提示信息。

> [!TIP]
> 这是一个技巧提示。

> [!WARNING]
> 这是一个警告信息。
```

---

### 4. 本地实时预览 (Live Watch & Serve)

支持实时监听文件变动并自动重新编译：

```bash
python3 scripts/generate_blog.py --serve
```

然后在浏览器中打开 `http://localhost:8000/blog.html` 即可实时预览。修改 Markdown、模版或 CSS 后，控制台将自动重构页面。

---

### 5. 编译整站与发布

单独生成静态 HTML 页面：

```bash
python3 scripts/generate_blog.py
```

生成结果将更新：
- 博客索引页：`blog.html`
- 文章详情页：`blog/<category>/<series>/<slug>.html`
- 文章配套静态资源目录：`blog/.../*.assets/`

提交修改并推送到 GitHub 即可自动发布到 GitHub Pages：

```bash
git add .
git commit -m "feat: publish new post"
git push origin <branch>
```
