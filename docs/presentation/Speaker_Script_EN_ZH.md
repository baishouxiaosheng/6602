# Game Gene Agent · 演讲稿（中英对照）

Final presentation, 27 November 2026 · PANG Junqing, LIU Tengxuan, GUO Yuchen, ZHENG Yufei

幻灯片讲解 5 分钟，合计约 4 分 40 秒，留 20 秒余量；之后切到浏览器做现场演示。
英文为实际讲稿，中文为对照。每页开头的时间是建议用时。

---

## Slide 1 · Title（约 20 秒）

**EN** Hello, we are Pang Junqing, Liu Tengxuan, Guo Yuchen and Zheng Yufei, presenting Game Gene Agent. It recommends Steam games by comparing nine design genes rather than genre tags, and it only shows a match when stored evidence supports it. We took the Another-Tool route: a FastAPI back end, a React front end, SQLite, the Steam Web API and Qwen.

**中** 大家好，我们是 Pang Junqing、Liu Tengxuan、Guo Yuchen、Zheng Yufei，今天介绍 Game Gene Agent。它不按类型标签，而是通过比较九个“设计基因”来推荐 Steam 游戏，并且只有在已保存的证据支持时才展示匹配。我们走的是“其他工具”路线：FastAPI 后端、React 前端、SQLite、Steam Web API 和通义千问。

---

## Slide 2 · Motivation（约 50 秒）

**EN** Three observations started the project. First, tag-based recommendations describe the surface of a game, so they return more of the genre you already play. Second, a chat model can give a convincing reason, but you cannot check it. Third, players actually choose by feel: challenge, pace, story. Those patterns cross genre lines. So our idea is to describe every game and every player with the same nine design genes on a zero-to-four scale, and to recommend only what stored evidence supports.

**中** 这个项目源于三点观察。第一，基于标签的推荐描述的是游戏的表层，所以只会给你更多已经在玩的类型。第二，聊天模型能给出听起来很有道理的理由，但你无法核实。第三，玩家其实是凭感受选游戏的：挑战、节奏、故事，而这些模式是跨类型的。所以我们的想法是：用同样的九个设计基因、0 到 4 的等级来描述每一款游戏和每一位玩家，并且只推荐有证据支持的结果。

---

## Slide 3 · Expected outcomes（约 55 秒）

**EN** What does the system deliver? Two tracks: familiar territory, and cross-genre discoveries with a compatible gene pattern. And we can measure it. Twenty-nine of thirty catalogue games are verified; the thirtieth stays partial because we do not guess. One hundred seventy-two evidence quotes are stored, one for every known gene level. In our live run with a real Steam library of forty-eight games, none of the owned games was recommended. Sixty-four automated tests pass. The card on the right is from that live run: Hollow Knight, a different genre, matched on three genes. The green pips are the game’s level and the outline is the player’s target; the supporting quotes open on demand, and its weak point is stated. Notice the run returned one game per track. The system leaves slots empty rather than lowering its thresholds.

**中** 系统交付什么？两条推荐轨道：熟悉的类型，以及基因模式相容的跨类型发现。而且这些都可以度量。目录 30 款游戏中 29 款通过核验，第 30 款保持“部分”状态，因为我们不猜测。系统保存了 172 条证据原句，每个已知的基因等级都有一条。在使用真实 Steam 游戏库（48 款游戏）的实测中，没有任何一款已拥有的游戏被推荐。64 个自动化测试全部通过。右侧的卡片就来自那次实测：Hollow Knight 属于不同类型，在三个基因上匹配。绿色色块是游戏的等级，白色描边是玩家的目标值；支持它的原句可以点开查看，同时注明了它的弱点。请注意那次运行每条轨道只返回了一款游戏：系统宁可留空，也不降低门槛。

---

## Slide 4 · Role of each scenario（约 70 秒）

**EN** Our three scenarios are three linked Python workflows. Workflow one builds the player profile: it ingests the questionnaire, an optional free-text request that Qwen parses and the user must confirm, and an optional public Steam library, which gives us favourites and the list of owned games to exclude. Workflow two builds the catalogue: captured Steam store facts and reviewed gene levels, each tied to an exact quote. If a gene has no evidence it stays null, and a weak game stays partial. Workflow three recommends: hard filters, a deterministic compatibility score, a split into two tracks, and then Qwen ranks only the candidates we supply. The workflows never call each other directly. They share state in SQLite through saved keys: profile ID, app ID, run ID and job ID.

**中** 我们的三个场景是三个相互关联的 Python 工作流。工作流一构建玩家画像：它接收问卷；可选的自由文本需求，由通义千问解析并且必须由用户确认；以及可选的公开 Steam 游戏库，从中得到偏爱的游戏和需要排除的已拥有游戏列表。工作流二构建游戏目录：采集到的 Steam 商店信息和经过人工审核的基因等级，每一项都对应一句原文。某个基因没有证据就保持为空，证据不足的游戏保持“部分”状态。工作流三负责推荐：硬过滤、确定性的相容度评分、划分为两条轨道，然后通义千问只对我们提供的候选进行排序。这些工作流从不直接互相调用，而是通过保存在 SQLite 里的键共享状态：画像 ID、游戏 AppID、运行 ID 和任务 ID。

---

## Slide 5 · Six parts（约 55 秒）

**EN** Because we chose another tool, here is how each required part is matched. The webhook is our FastAPI endpoints. The router is the hard filters, the threshold and the track split, which lead to three different outcomes. The data store is SQLite. For error handling, Steam calls retry three times with backoff, and an invalid model ranking gets exactly one repair attempt before the job is marked failed and shown to the user. OpenRouter is replaced by a Qwen adapter with an OpenAI-compatible interface. The principle from the course that shaped the design is on the right: the AI recommends, the rules decide. Code runs before the model, constrains what the model may see and cite, and checks everything after it.

**中** 因为我们选择了其他工具，这里说明六项要求各自如何对应。Webhook 对应我们的 FastAPI 端点。路由器对应硬过滤、阈值和轨道划分，它们会导向三种不同的结果。数据存储是 SQLite。错误处理方面，Steam 请求会带退避地重试三次；模型给出的无效排序只有一次修复机会，之后任务会被标记为失败并展示给用户。OpenRouter 由一个兼容 OpenAI 接口的通义千问适配层替代。右侧是课程里塑造了我们设计的原则：AI 给建议，规则做决定。代码在模型之前运行，限定模型能看到和能引用的内容，并在模型之后检查一切。

---

## Slide 6 · Live demo（约 30 秒，然后切到浏览器）

**EN** The demo follows four steps. A questionnaire with nine sliders. An optional Steam library import. A profile summary to review the nine targets and priorities. And the recommendations, with the match score, the reason and the evidence quotes. The limits today are a thirty-game catalogue, English store text, and gene levels reviewed by hand. Let us show it running.

**中** 演示分四步：九个滑块的问卷；可选的 Steam 游戏库导入；用于确认九个目标值和优先项的画像总览；以及带有匹配度、理由和证据原句的推荐结果。目前的局限是：目录只有 30 款游戏、只使用英文商店文本、基因等级由人工审核。下面我们实际运行给大家看。

---

## 现场演示提示（3 分钟）

1. 演示前先确认页面右上角显示 **Backend connected**，并提前在教室电脑的浏览器里打开页面。
2. 问卷：拖动两三个滑块、勾选一到两个 High priority，点击 **Build player profile**。
3. Steam 库：时间紧就点 **Skip Steam import**；想展示排除已拥有游戏，就提前准备好一个公开资料的 SteamID64。
4. 画像页：指出雷达图和绿色的优先项，点击 **Generate recommendations**（通义千问排序可能需要几十秒，这段时间可以讲“规则先行、模型只排序”）。
5. 结果页：指着一条跨类型推荐，读出一条证据原句，说明匹配度是程序算的、不是模型给的。
