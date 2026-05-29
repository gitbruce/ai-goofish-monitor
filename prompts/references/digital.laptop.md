---
id: digital.laptop
version: 1.0
schema_fields:
  - {name: model_chip,        type: object, required: true}
  - {name: battery_health,    type: object, required: true}
  - {name: condition,         type: object, required: true}
  - {name: history,           type: object, required: true}
  - {name: seller_type,       type: object, required: true}
  - {name: shipping,          type: object, required: true}
  - {name: seller_credit,     type: object, required: true}
  - {name: manual_questions,  type: array,  required: true}
generation_hints:
  must_include_sections:
    - "第一部分：核心分析原则"
    - "第二部分：详细分析指南"
    - "第三部分：危险信号与豁免条款"
    - "第四部分：manual_questions 生成指南"
---

# 二手笔记本电脑参考

## 分析原则

### 画像优先原则 (PERSONA-FIRST PRINCIPLE) [V6.3 核心升级]
这是解决"高级玩家"与"普通贩子"识别混淆的最高指导原则。在评估卖家时，你的首要任务不是寻找孤立的疑点，而是**构建一个连贯的卖家"行为画像"**。你必须回答核心问题："这个卖家的所有行为（买、卖、评价、签名）组合起来，讲述的是一个怎样的故事？"

- 如果故事是连贯的个人行为（例如，一个热爱数码产品，不断体验、升级、出掉旧设备的发烧友），那么一些表面上的"疑点"可以被合理解释，不应作为否决依据
- 如果故事是矛盾的、不连贯的，或者明确指向商业行为（例如，购买记录是配件和坏机，售卖记录却是大量"几乎全新"的同型号机器），那么即便卖家伪装得很好，也必须判定为商家

### 一票否决硬性原则 (HARD DEAL-BREAKER RULES)
以下为通用底线，具体型号/芯片由用户需求决定：
- **型号/芯片**：必须符合用户指定的型号和芯片要求
- **卖家信用**：必须为"卖家信用极好"
- **邮寄方式**：必须支持邮寄
- **电池健康硬性门槛**：若明确提供了电池健康度，其数值必须 ≥ 90%（用户另有要求的除外）
- **机器历史**：不得出现任何"维修过"、"更换过部件"、"有暗病"等明确表示有拆修历史的描述

### 图片至上原则 (IMAGE-FIRST PRINCIPLE)
图片信息与文本描述冲突时，以图片信息为最终裁决依据。

### 信息缺失处理原则 (MISSING-INFO HANDLING)
对于可后天询问的关键信息（特指电池健康度和维修历史），若完全未找到，状态应为 NEEDS_MANUAL_CHECK，不直接否决。如果卖家画像极为优秀，可以进行"有条件推荐"。

## 详细分析指南

### model_chip
核对所有文本和图片。型号和芯片必须符合用户要求，不符合则 FAIL。

### battery_health
健康度 ≥ 90%（或用户指定值）。若无信息，则为 NEEDS_MANUAL_CHECK。

### condition
最多接受"细微划痕"。仔细审查图片四角、A/D面。

### history
严格审查所有文本和图片，寻找"换过"、"维修"、"拆过"、"进水"、"功能不正常"等负面描述。若完全未提及，则状态为 NEEDS_MANUAL_CHECK；若有任何拆修证据，则为 FAIL。

### seller_type - 决定性评估
运用画像优先原则，判定卖家是【个人玩家】还是【商家/贩子】。

危险信号清单（Red Flag List）及豁免条款：
- **交易频率**：短期内密集交易
  - 发烧友豁免：时间跨度超过2年，买卖行为形成"体验-升级-出售"闭环
- **商品垂直度**：高度集中于某一特定型号
  - 发烧友豁免：该领域深度玩家，专注于某系列是专业性体现
- **行话**："同行、工作室、拿货、量大从优"等术语
  - 无豁免，强烈商家信号
- **物料购买**：批量配件、维修工具、坏机
  - 无豁免，决定性商家证据
- **图片/标题风格**：背景高度统一、专业；标题模板化
  - 发烧友豁免：追求完美展示心爱物品

### shipping
"仅限xx地面交/自提"则 FAIL。

### seller_credit
必须为"卖家信用极好"。

## manual_questions 生成指南
把所有缺失或需追问的项汇总到 manual_questions 数组。例如：
- 电池健康度截图
- 维修/拆机历史确认
- 具体配置参数确认
