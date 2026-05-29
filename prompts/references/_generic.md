---
id: generic
version: 1.0
schema_fields:
  - {name: product_condition, type: object, required: true}
  - {name: completeness,     type: object, required: true}
  - {name: seller_type,      type: object, required: true}
  - {name: shipping,         type: object, required: true}
  - {name: price_value,      type: object, required: true}
  - {name: manual_questions, type: array,  required: true}
generation_hints:
  must_include_sections:
    - "第一部分：核心分析原则"
    - "第二部分：详细分析指南"
    - "第三部分：危险信号与豁免条款"
    - "第四部分：manual_questions 生成指南"
---

# 通用二手商品参考

## 分析原则

### 画像优先原则 (PERSONA-FIRST PRINCIPLE)
评估卖家时，首要任务是构建连贯的卖家"行为画像"。回答核心问题：这个卖家的所有行为组合起来，讲述的是一个怎样的故事？

- 如果故事是连贯的个人行为（例如，不断体验、升级、出掉旧设备），那么表面疑点可被合理解释
- 如果故事是矛盾的或明确指向商业行为（例如，购买配件和坏机，售卖大量"几乎全新"的同型号），必须判定为商家

### 一票否决硬性原则
根据用户指定的具体需求设定。以下为通用底线：
- 卖家信用等级必须为"极好"
- 必须支持邮寄（除非用户明确要求面交）

### 图片至上原则
图片信息与文本描述冲突时，以图片信息为最终裁决依据。

### 信息缺失处理原则
可后天询问的关键信息若完全未找到，状态应为 NEEDS_MANUAL_CHECK，不直接否决。

## 详细分析指南

### product_condition
检查商品成色、外观、功能完好度。对照图片和文本描述综合判断。

### completeness
检查配件、原包装、说明书等齐全度。

### seller_type
运用画像优先原则，判定个人玩家还是商家。

危险信号：
- 交易频率：短期内密集交易
- 商品垂直度：高度集中于某一特定型号
- 行话：描述中出现"同行、工作室、拿货、量大从优"
- 物料购买：批量配件、维修工具

豁免条款：
- 长期发烧友（2年以上交易跨度）
- 领域深度玩家（买卖行为形成"体验-升级-出售"闭环）

### shipping
检查是否支持邮寄。"仅限xx地面交/自提"则 FAIL。

### price_value
与市场公允价比对。异常低价为强红旗。

## manual_questions 生成指南
把所有缺失或需追问的项汇总到 manual_questions 数组。
