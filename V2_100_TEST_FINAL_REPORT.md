# Risk News Monitor V2.1：全新 100 家公司端到端测试最终报告

所有新闻和事件仍为 `UNVERIFIED` 候选。本报告是技术压力测试，不构成信用评级或风险结论。

## 1. 全流程实际统计

| Metric | Value |
|---|---:|
| Articles With V1 Extraction Record | 108 |
| Candidate Negative Events | 31 |
| Cleaned | 18 |
| Duplicate Articles | 0 |
| Entity Matched | 56 |
| Entity Uncertain | 55 |
| Invalid Full Text | 0 |
| Malformed Extraction Records | 0 |
| Missing Full Text | 46 |
| Needs Review | 74 |
| No Candidate Found | 58 |
| Rejected | 39 |
| Search Completed | 100 |
| Search Partial | 0 |
| Total Articles Processed | 131 |
| Total Companies | 100 |
| Total RSS Candidates | 131 |
| Unrelated Articles | 20 |
| V1 Full Text Success | 85 |
| Valid Full Text | 83 |
| V1 正文 SUCCESS 率 | 78.7% |
| V2 有效正文率（按已尝试提取） | 76.9% |
| 重大风险待核实线索 | 0 |

## 2. 错误与修复报告

| Issue ID | Problem | Root Cause | Fix Applied | Regression Test | Current Status |
|---|---|---|---|---|---|
| V21-LIVE-009 | CMB acronym matched Capital Markets Board as China Merchants Bank | Positive word 'capital' overrode an explicit conflicting expanded entity name | Added Capital Markets Board/SPK conflicts and made explicit conflicting entity context conservative | test_cmb_acronym_does_not_override_capital_markets_board_context | FIXED |
| V21-LIVE-008 | Bank of China matched the People's Bank of China substring | A shorter bank name was accepted inside a different central-bank legal name | Added central-bank conflicting contexts and prioritized explicit conflicts unless a strong legal name is present | test_bank_of_china_does_not_match_peoples_bank_of_china_substring | FIXED |
| V21-LIVE-007 | Active 'suing' wording missed a filed pollution case | Litigation grammar covered sued/filed but not present-participle wording | Added active suing language to filed-litigation detection | test_company_currently_being_sued_is_litigation_candidate | FIXED |
| V21-LIVE-006 | Vehicle recall wording was only possibly relevant | Operating-risk rules recognized 'product recall' but not recall verb forms with vehicle counts | Added bounded recall verb/noun patterns for vehicles, cars, products and units | test_vehicle_recall_wording_is_operating_risk | FIXED |
| V21-LIVE-005 | 'Cut 2,300 jobs' word order was missed | Operating-risk rules only recognized layoff and noun-form job-cut phrases | Added numeric cut-jobs verb pattern | test_job_cut_word_order_is_operating_risk | FIXED |
| V21-LIVE-004 | Forward-looking risk boilerplate created false negative-news candidates | Screening treated hypothetical disclosure tails as observed events | Exclude trailing forward-looking boilerplate from event screening while retaining title and article lead | test_forward_looking_boilerplate_does_not_turn_dividend_release_negative | FIXED |
| V21-LIVE-003 | Aircraft braking fault was only possibly relevant | Operating-risk rules lacked transport safety fault and serious-incident patterns | Added deterministic braking-fault, tyre-burst and serious-incident patterns | test_aircraft_braking_fault_serious_incident_is_operating_risk | FIXED |
| V21-LIVE-002 | Money-laundering class action was classified as non-negative | Rules missed class-action suit wording, plural regulators and money-laundering terminology | Expanded litigation, enforcement and governance patterns | test_money_laundering_class_action_is_a_negative_candidate | FIXED |
| V21-LIVE-001 | Non-GBK legal name crashed Windows progress output | Progress messages wrote Unicode legal names directly to a GBK console | Added encoding-safe console rendering with reversible backslash escapes | test_console_safe_replaces_unencodable_legal_name_for_gbk_stream | FIXED |
| V21-DEV-001 | Person/company homonym could create direct entity match | Single-token company aliases lacked negative person/entertainment context | Added contextual ambiguity guards including Safran/Peter Safran | test_safran_film_producer_is_not_aerospace_company_match | FIXED |
| V21-DEV-002 | Negated layoffs could be classified as operating risk | Keyword matches did not inspect local negation context | Added English and Chinese local-negation filtering | test_no_layoffs_negation_does_not_create_operating_risk | FIXED |
| V21-DEV-003 | Narrowing losses could be classified as financial deterioration | Loss phrase rules ignored positive direction and earnings context | Added positive financial direction guards with negative overrides | test_narrowing_losses_and_positive_results_are_not_financial_deterioration | FIXED |
| V21-DEV-004 | Large RSS/article date conflicts could enter CLEANED | Date validation was recorded but absent from the routing gate | Route date conflicts to NEEDS_REVIEW | test_date_conflict_routes_otherwise_clean_candidate_to_review | FIXED |
| V21-DEV-005 | New-catalog bilingual aliases were unavailable to entity resolution | V2 profiles were limited to the historical built-in 300 | Load structured catalog metadata from the acquisition directory | test_pipeline_loads_catalog_aliases_from_acquisition_directory | FIXED |

当前开放问题数：0。逐条机器可读记录见 `test_issues.csv`。

## 3. V1 与 V2 结果比较

| Metric | 历史 300 家 V2 | 本轮新 100 家 V2.1 |
|---|---:|---:|
| Total Companies | 300 | 100 |
| Total RSS Candidates | 856 | 131 |
| Articles With V1 Extraction Record | 559 | 108 |
| V1 Full Text Success | 355 | 85 |
| Valid Full Text | 341 | 83 |
| Cleaned | 108 | 18 |
| Needs Review | 252 | 74 |
| Rejected | 496 | 39 |
| Candidate Negative Events | 169 | 31 |

两轮公司样本、地域、行业和新闻周期不同，比例变化不能直接解释为算法质量提升或下降。

## 4. 真实新闻抽样

抽样按 `SHA-256(bucket + association_id + title)` 固定排序，最多选择 15 条 Cleaned、15 条 Needs Review、10 条 Rejected；若数量不足则检查该类全部记录。完整证据见 `sample_review.csv`。

| Bucket | Rank | Company | Title | Entity | Negative | Content | Date |
|---|---:|---|---|---|---|---|---|
| CLEANED | 1 | Lenovo Group Limited | Netlist opens new legal offensive with ITC and federal court complaints - World IP Review | MATCHED/DIRECT/0.72 | NEGATIVE_CANDIDATE: 重大诉讼 | VALID/80: paywall/login marker: purchase a subscription | CONSISTENT: RSS and article dates differ by 61182 seconds; within tolerance |
| CLEANED | 2 | Carrefour SA | Hackers hit supermarket fridges across Europe again, three weeks after France - MarketScale | MATCHED/DIRECT/0.72 | NEGATIVE_CANDIDATE: 经营与业务风险 | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 54415 seconds; within tolerance |
| CLEANED | 3 | Telefónica, S.A. | Virgin Media O2 to cut thousands of jobs in major cost-saving drive - Silicon Republic | MATCHED/DIRECT/0.72 | NEGATIVE_CANDIDATE: 经营与业务风险 | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 63605 seconds; within tolerance |
| CLEANED | 4 | Comcast Corporation | Fox Now Owns Roku & Changes Roku’s CEO, Comcast Massive Layoffs, & More – Your Top Cord Cutting Stories - / Cord Cutters News | MATCHED/DIRECT/0.9 | NEGATIVE_CANDIDATE: 经营与业务风险 | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 47439 seconds; within tolerance |
| CLEANED | 5 | Zijin Mining Group Company Limited | Congo residents sue Chinese copper mine over alleged pollution, statement says - KELO-AM | MATCHED/DIRECT/0.72 | NEGATIVE_CANDIDATE: 重大诉讼 | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 55274 seconds; within tolerance |
| CLEANED | 6 | Comcast Corporation | Comcast planning major layoffs as part of its restructuring: Report - LiveNOW from FOX | MATCHED/DIRECT/0.9 | NEGATIVE_CANDIDATE: 经营与业务风险 | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 62163 seconds; within tolerance |
| CLEANED | 7 | Zijin Mining Group Company Limited | Zijin Mining DRC Pollution Lawsuit Cobalt Risk - Rare Earth Exchanges | MATCHED/DIRECT/0.9 | NEGATIVE_CANDIDATE: 重大诉讼 | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 103387 seconds; within tolerance |
| CLEANED | 8 | Banco Santander, S.A. | INVESTOR ALERT: Pomerantz Law Firm Investigates Claims On Behalf of Investors of Banco Santander, S.A. - SAN - PR Newswire | MATCHED/DIRECT/0.9 | NEGATIVE_CANDIDATE: 欺诈及公司治理 | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 8820 seconds; within tolerance |
| CLEANED | 9 | The Toronto-Dominion Bank | Ontario court certifies class-action suit against TD Bank regarding money laundering - CityNews Toronto | MATCHED/DIRECT/0.9 | NEGATIVE_CANDIDATE: 欺诈及公司治理; 重大诉讼 | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 81060 seconds; within tolerance |
| CLEANED | 10 | Royal Bank of Canada | Ex-RBC worker admits fraud after opening at least 43 accounts - Human Resources Director | MATCHED/DIRECT/0.9 | NEGATIVE_CANDIDATE: 欺诈及公司治理 | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 50289 seconds; within tolerance |
| CLEANED | 11 | Carrefour SA | Why Europe’s supermarket fridges were easy targets - The Mighty 790 KFGO | MATCHED/DIRECT/0.72 | NEGATIVE_CANDIDATE: 经营与业务风险 | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 61804 seconds; within tolerance |
| CLEANED | 12 | Banco Santander, S.A. | Pomerantz LLP investigates Banco Santander over Q3 earnings miss and rising credit risks. - Pluang | MATCHED/DIRECT/0.9 | NEGATIVE_CANDIDATE: 欺诈及公司治理 | VALID/85: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 83331 seconds; within tolerance |
| CLEANED | 13 | Zijin Mining Group Company Limited | Congo Residents Sue Chinese Copper Mine Over Alleged Pollution, Statement Says - The China-Global South Project | MATCHED/DIRECT/0.72 | NEGATIVE_CANDIDATE: 重大诉讼 | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 60195 seconds; within tolerance |
| CLEANED | 14 | Tesco PLC | Food recall: Tesco and Waitrose recall soup over fears tins could rupture — 'do not eat!' - GB News | MATCHED/DIRECT/0.9 | NEGATIVE_CANDIDATE: 经营与业务风险 | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 59315 seconds; within tolerance |
| CLEANED | 15 | Hyundai Motor Company | Hyundai Facing Lawsuit Over Driver Monitoring Setup That Allegedly Can Be Fooled by Laughter, Makeup - Road & Track | MATCHED/DIRECT/0.9 | NEGATIVE_CANDIDATE: 重大诉讼 | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 58860 seconds; within tolerance |
| NEEDS_REVIEW | 1 | Telefónica, S.A. | Telefonica stock faces UK reset as Virgin Media O2 targets GBP 800m savings - ad-hoc-news.de | MATCHED/DIRECT/0.9 | POSSIBLY_RELEVANT: none | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 39025 seconds; within tolerance |
| NEEDS_REVIEW | 2 | Philip Morris International Inc. | Business activity rebounds after two sluggish months: PMI - The Daily Star | UNCERTAIN/UNCERTAIN/0.48 | NEEDS_REVIEW: none | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 22692 seconds; within tolerance |
| NEEDS_REVIEW | 3 | Mitsui & Co., Ltd. | Mitsui Chemicals to Acquire JSR in $11.6 Billion Deal as Japan Bolsters Chip Industry - PYMNTS.com | UNCERTAIN/UNCERTAIN/0.48 | NEEDS_REVIEW: none | UNAVAILABLE/0: no extracted text; fetch_status=NOT_SELECTED | RSS_ONLY: article publication date unavailable; using RSS timestamp |
| NEEDS_REVIEW | 4 | AXA S.A. | Kunle Ahmed positions AXA Mansard for stronger market leadership - Business News Nigeria | UNCERTAIN/UNCERTAIN/0.48 | NEEDS_REVIEW: none | UNAVAILABLE/0: no extracted text; fetch_status=HTTP_ERROR | RSS_ONLY: article publication date unavailable; using RSS timestamp |
| NEEDS_REVIEW | 5 | Mitsui & Co., Ltd. | Mitsui Joins Bank To Buy Chip Materials Maker For $11.6B - Law360 | UNCERTAIN/UNCERTAIN/0.48 | NEEDS_REVIEW: 破产、重组及债务调整 | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 65603 seconds; within tolerance |
| NEEDS_REVIEW | 6 | Mitsui & Co., Ltd. | Mitsui Sumitomo launches construction, cargo business in U.K. - Business Insurance | UNCERTAIN/UNCERTAIN/0.48 | NEEDS_REVIEW: none | UNAVAILABLE/0: no extracted text; fetch_status=NOT_SELECTED | RSS_ONLY: article publication date unavailable; using RSS timestamp |
| NEEDS_REVIEW | 7 | Mitsui & Co., Ltd. | Japan’s semiconductor materials giant is born: Mitsui Chemicals to acquire JSR for 16 trillion won - 파이낸셜뉴스 | MATCHED/DIRECT/0.9 | POSSIBLY_RELEVANT: none | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 11451 seconds; within tolerance |
| NEEDS_REVIEW | 8 | Tesco PLC | Popular soup urgently recalled from Tesco and Waitrose with 'do not eat' warning - Daily Express | UNCERTAIN/UNCERTAIN/0.48 | NEEDS_REVIEW: 经营与业务风险 | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 34380 seconds; within tolerance |
| NEEDS_REVIEW | 9 | The Walt Disney Company | Fired Healey Aide Indicted for Second Wire Fraud After Allegedly Using SNAP for Disney Trip While Facing Cocaine Charges - New Bedford Guide | UNCERTAIN/UNCERTAIN/0.48 | NEEDS_REVIEW: 欺诈及公司治理 | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 90762 seconds; within tolerance |
| NEEDS_REVIEW | 10 | Bank of China Limited | Bank of China stock faces new foreign-currency policy backdrop - ad-hoc-news.de | MATCHED/DIRECT/0.9 | POSSIBLY_RELEVANT: none | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 53709 seconds; within tolerance |
| NEEDS_REVIEW | 11 | Münchener Rückversicherungs-Gesellschaft Aktiengesellschaft | Munich Re's €6.6 Billion Profit Test: JPMorgan Steps Aside Before the November 12 Verdict - ad-hoc-news.de | UNCERTAIN/UNCERTAIN/0.48 | NEEDS_REVIEW: none | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 61914 seconds; within tolerance |
| NEEDS_REVIEW | 12 | Ryanair Holdings plc | Ryanair aircraft tyres burst on landing after braking system fault, investigation finds - BreakingNews.ie | MATCHED/DIRECT/0.9 | NEGATIVE_CANDIDATE: 经营与业务风险 | VALID/100: article-like text structure; fetch_status=SUCCESS | CONFLICT: RSS and article dates differ by 7643186 seconds; sources conflict; RSS retained as monitoring timestamp |
| NEEDS_REVIEW | 13 | Telefonaktiebolaget LM Ericsson | Asus Skirts Sales Ban With FRAND Defense Against Ericsson - Law360 | UNCERTAIN/UNCERTAIN/0.48 | NEEDS_REVIEW: 破产、重组及债务调整 | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 64130 seconds; within tolerance |
| NEEDS_REVIEW | 14 | Canadian Natural Resources Limited | Canadian Natural Resources Limited Announces 2026 Third Quarter Results - BOE Report | MATCHED/DIRECT/0.9 | POSSIBLY_RELEVANT: none | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 32400 seconds; within tolerance |
| NEEDS_REVIEW | 15 | Tesco PLC | Police launch investigation into burglary at a Tesco Express store in Narborough - Leicester Media Online | UNCERTAIN/UNCERTAIN/0.48 | NEEDS_REVIEW: none | VALID/95: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 58819 seconds; within tolerance |
| REJECTED | 1 | POSCO Holdings Inc. | Brahmapur Police Files Chargesheet in POCSO Case Involving Two Minor Sisters; Action Taken Over Alleged Intimidation of Victims - Odisha Barta | UNRELATED/UNRELATED/0.05 | UNRELATED: none | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 17363 seconds; within tolerance |
| REJECTED | 2 | Carrefour SA | France blames Iran-linked hackers for supermarket fridge attack, vows sanctions - KFOX | UNRELATED/UNRELATED/0.05 | UNRELATED: none | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 66199 seconds; within tolerance |
| REJECTED | 3 | Carrefour SA | France blames Iran for a cyberattack that heated supermarket refrigerators - Newsday | UNRELATED/UNRELATED/0.05 | UNRELATED: none | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 72852 seconds; within tolerance |
| REJECTED | 4 | Brookfield Corporation | Brookfield Corporation (BN) stock price, news, quote and history - Yahoo Finance Australia | MATCHED/DIRECT/0.9 | NOT_NEGATIVE: none | VALID/100: article-like text structure; fetch_status=SUCCESS | CONFLICT: RSS and article dates differ by 183655 seconds; sources conflict; RSS retained as monitoring timestamp |
| REJECTED | 5 | Carrefour SA | Majid Al Futtaim launches its SHARE rewards program at Carrefour, replacing MyClub - HapaKenya - | MATCHED/DIRECT/0.9 | NOT_NEGATIVE: none | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 46129 seconds; within tolerance |
| REJECTED | 6 | Canadian Natural Resources Limited | Canadian Natural Resources Limited Dividend Outlook: What the Latest Results Say About TSX:CNQ Income Safety - kalkine.ca | MATCHED/DIRECT/0.82 | NOT_NEGATIVE: none | UNAVAILABLE/0: no extracted text; fetch_status=ROBOTS_UNAVAILABLE | RSS_ONLY: article publication date unavailable; using RSS timestamp |
| REJECTED | 7 | O'Reilly Automotive, Inc. | 2026 NASCAR O’Reilly Auto Parts Series winners - NASCAR.com | MATCHED/DIRECT/0.9 | NOT_NEGATIVE: none | VALID/85: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 57600 seconds; within tolerance |
| REJECTED | 8 | O'Reilly Automotive, Inc. | Allgaier’s resilience yields second O’Reilly Series title in three years - NASCAR.com | MATCHED/DIRECT/0.72 | NOT_NEGATIVE: none | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 100581 seconds; within tolerance |
| REJECTED | 9 | Bank of China Limited | People’s Bank of China Halts Solana Shanghai Event Over Unauthorized Crypto Promotion: 7 outlets compared - NewsCord | UNRELATED/UNRELATED/0.15 | UNRELATED: none | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 62627 seconds; within tolerance |
| REJECTED | 10 | Sea Limited | Investigation under way into migrant deaths at sea - eKathimerini.com | UNRELATED/UNRELATED/0.15 | UNRELATED: none | VALID/100: article-like text structure; fetch_status=SUCCESS | CONSISTENT: RSS and article dates differ by 40296 seconds; within tolerance |

## 5. 最终结论

1. **Python + Google News RSS 能否可靠批量检索？** 本批所有公司均完成请求；RSS 仍可能漏报、截断或限流，不能当作完整新闻数据库。
2. **正文获取情况？** 已尝试 108 篇，V1 SUCCESS 85 篇（78.7%），V2 验证为有效正文 83 篇（76.9%）。
3. **V2 是否降低误报？** V2 通过实体、正文、语义和日期门槛把记录分流，但没有人工标注金标准，分流比例只能证明过滤发生，不能单独证明准确率提升。
4. **仍需 LLM 或人工核实什么？** 实体不确定、多义品牌、缺失正文、否定/比较语义、旧闻更新、同事件归并和严重风险线索均需复核。
5. **能否作为未来 Risk Intelligence Skill 3 底层引擎？** 具备可续跑采集、合规正文获取、审计和结构化候选输出的技术基础；上线前仍需权威实体库、标注评测集、稳定新闻源、权限治理和人工复核闭环。
