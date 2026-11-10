# 300 家公司负面新闻监控系统 V2.0

V2 在现有 Google News RSS 与正文抓取结果之上增加一层**离线、确定性、可审计**的数据清洗。它不会把关键词命中当作已确认风险，也不会把 `fetch_status == SUCCESS` 直接当作有效正文。

## V2.1：全新 100 家公司压力测试

V2.1 支持从结构化公司目录运行同一条采集与清洗链路。仓库内的 `test_new_100/company_list_100.csv` 含 100 家与历史 300 家不重叠的公开公司，目录审计见 `test_new_100/company_list_audit.json`。

真实联网运行（会遵守 robots.txt、登录和付费墙限制）：

```cmd
python run_new_100_test.py --allow-network --delay 3 --days 7 --per-company 5
```

若采集已经完成，只重新执行确定性质量审计：

```cmd
python run_new_100_test.py --audit-only
```

结果写入 `results_new_100_v2/`，最终报告同时写入根目录 `V2_100_TEST_FINAL_REPORT.md`。本次 2026-11-10 实测完成 100/100 家请求，获取 131 条 RSS 候选，V1 尝试提取 108 条、成功 85 条，V2 有效正文 83 条；最终分流为 Cleaned 18、Needs Review 74、Rejected 39。`NO_CANDIDATE_FOUND` 只表示本次查询和窗口没有保留候选，不能解释为公司没有风险。

## 推荐：清洗现有结果（不联网）

```cmd
python run_pipeline.py --mode clean-existing --input results_full_300 --output results_full_300_v2
```

这会读取已有 `negative_news_candidates.csv`、`coverage_300.csv` 和 `articles_with_content.jsonl`，保留 V1 原始目录不变，并生成：

```text
results_full_300_v2/
├── company_coverage.csv
├── articles_cleaned.jsonl
├── articles_rejected.jsonl
├── articles_needs_review.jsonl
├── events_candidates.jsonl
├── article_source_mapping.csv
├── pipeline_audit.json
├── quality_report.md
└── pipeline.log
```

核心状态定义：

- `content_validation_status`：`VALID`、`PARTIAL`、`INVALID`、`UNAVAILABLE`、`NEEDS_REVIEW`。
- `entity_relationship`：`DIRECT`、`SUBSIDIARY`、`PARENT_GROUP`、`INDIRECT`、`UNRELATED`、`UNCERTAIN`。
- `negative_screening_status`：`NEGATIVE_CANDIDATE`、`POSSIBLY_RELEVANT`、`NOT_NEGATIVE`、`UNRELATED`、`NEEDS_REVIEW`。
- `event_confidence` 始终从 `UNVERIFIED` 开始，后续 Agent 必须核实来源和事实。

只有同时满足以下条件的关联才进入 `articles_cleaned.jsonl`：正文为 `VALID`、实体证据充分、主体关系受支持、负面筛选为 `NEGATIVE_CANDIDATE`。不确定项进入 `articles_needs_review.jsonl`；明确无效、无关或非负面项进入 `articles_rejected.jsonl`。

## 完整流程（需要明确授权联网）

```cmd
python run_pipeline.py --mode full --limit 300 --days 7 --per-company 5 --allow-network
```

`full` 会把 RSS 搜索和正文抓取写入独立的 `results_full_300_refresh`，继续使用 V1 检查点，然后执行相同的 V2 清洗。没有 `--allow-network` 时命令会拒绝运行。系统不绕过 robots.txt、登录、付费墙、验证码或反爬机制。

## 后续 Agent 读取建议

- 首选 `articles_cleaned.jsonl` 获取通过正文质量门槛的候选证据。
- 用 `events_candidates.jsonl` 聚合同主体、类别、日期和关键事实相近的报道，但不能把 `event_id` 当作事实已确认。
- 对 `articles_needs_review.jsonl` 做实体、语义、日期和来源复核。
- 用 `pipeline_audit.json` 与 `company_coverage.csv` 核对范围和缺口。
- 不要仅依据标题、缺失正文、抓取失败或 `SEARCH_QUERY_ONLY` 生成信用风险结论。

## 测试

```cmd
python -m pytest -q
```

测试完全离线，覆盖正常正文、挑战页、付费墙、实体歧义、中英文别名、多公司报道、`by default`、股票与信用评级、重复正文、日期冲突、访问受限和替代来源关联。

---

## V1：Google News RSS + 新闻正文抓取（Agent 读取版）

本项目内置 **300 家公开演示公司** 的名单。`search_300_companies.py` 用 Google News RSS 搜索标题；`extract_article_bodies.py` 把已经搜到的新闻链接转换成原始媒体链接，并尽可能抓取正文，供后续 Agent 从 JSONL 文件读取。

> 核心区别：RSS **没有新闻正文**；解析 Google News 链接后还需要访问媒体网站。不是所有网站都允许自动抓取。**成功抓取正文 != 负面事件已经核实。**

## Windows CMD / VS Code 运行

若你已经使用上个版本搜索了300家公司：只需把本 ZIP 内的 `extract_article_bodies.py` 和新的 `requirements.txt` **复制到原来的 `risk_300_ready` 目录**，保留原来的 `results_300_google_rss` 文件夹。不要覆盖或删除其中的新闻结果和检查点。

你的示例目录：

```text
C:\Users\sbq30\Desktop\risk_news_300_companies_ready\risk_300_ready\
    search_300_companies.py
    extract_article_bodies.py         <-- 新增
    requirements.txt                 <-- 替换
    results_300_google_rss\
        negative_news_candidates.csv <-- 现有爬虫已生成的文件
        coverage_300.csv
```

进入上述 `risk_300_ready` 目录后执行：

```cmd
python -m pip install -r requirements.txt
python extract_article_bodies.py --per-company 3 --max-total 10
```

这是**先提取最多10篇文章试效果**，可以检查正文是否真的抓到了。确认后运行：

```cmd
python extract_article_bodies.py --per-company 5
```

默认每家公司最多提取 **5 篇候选新闻正文**；300 家都有候选时理论最多 1500 篇。第二次运行自动跳过已处理文章；如要重试失败项：

```cmd
python extract_article_bodies.py --per-company 5 --retry-failed
```

如果你还没有 RSS 新闻数据，先跑：

```cmd
python search_300_companies.py
python extract_article_bodies.py --per-company 5
```

## 主要输出（均在 results_300_google_rss 目录内）

| 文件 | 说明 |
|---|---|
| `articles_with_content.jsonl` | **Agent 主要输入**：每行一个 JSON，包含 `company`, `title`, `publisher`, `published_utc`, `google_news_url`, `original_url`, `final_url`, `full_text`, `fetch_status`, `confidence` 等 |
| `articles_with_content.csv` | 便于直接在 Excel 打开，含 `Full Text`，长正文建议以 JSONL 为准 |
| `article_text_coverage_300.csv` | 每家公司选中数、成功抓取正文数、失败数、待处理数，以及之前 RSS 检索状态 |
| `article_fetch_summary.json` | 按抓取状态汇总 |
| `article_fetch_checkpoints.jsonl` | 每篇文章的抓取检查点；中断后可继续，不要随意删除 |

`fetch_status` 常见状态：`SUCCESS`（提取了足够长的正文）、`SHORT_TEXT`（正文过短，可能为摘要或订阅页）、`RESOLVE_FAILED`（Google News 链接未能解析）、`ROBOTS_BLOCKED`、`ROBOTS_UNAVAILABLE`、`ACCESS_DENIED`、`EXTRACTION_FAILED`、`HTTP_ERROR`、`RATE_LIMITED`。

## 注意事项

- Google News 的 URL 解码机制属于**非公开、可能变化的接口**。本版本使用 `gnews-decoder==0.1.1`，失败会标明原因并保留原 Google News URL。不要将失效链接、抓取失败视为“无负面新闻”。
- `trafilatura` 只提取页面可访问的正文，不登录、不破解付费墙、不使用代理绕过限制。爬虫检查 `robots.txt`，拒绝访问或无法核实规则时不会抓取。
- 每家公司默认仅抓取前5篇**候选新闻**，并非全量文章；RSS 原搜索本身也可能漏报。同名公司/标题误判仍需 Agent/人工核查。
- 不要把公司内部持仓、未经许可的发行人名单或具有使用限制的版权全文直接发送给外部模型。这里只使用 300 家公开演示名单；正式上线前需确认访问、留存和模型处理权限。
- 原来的 `search_window.json` 固定了7天窗口；下一次想重新检索新一周的新闻，请为 RSS 搜索指定新的 `--output` 文件夹；正文提取器用 `--input` 指向对应的新 CSV。

## 进阶参数

```cmd
python extract_article_bodies.py --input "C:\path\to\negative_news_candidates.csv" --per-company 10 --delay 3
python extract_article_bodies.py --dry-run
```

先读取 `article_text_coverage_300.csv` 确认确实抓到了正文，再把 `articles_with_content.jsonl` 作为 Agent 的输入。**不要**只凭 RSS 的标题或 `SEARCH_QUERY_ONLY` 断言发生负面事件。
