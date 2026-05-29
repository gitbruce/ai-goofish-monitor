---
id: bicycle.road
version: 1.0
schema_fields:
  - {name: product_form,         type: enum,   values: [frameset, complete_bike, ambiguous], required: true}
  - {name: model_version,        type: object, required: true}
  - {name: frame_size_fit,       type: object, required: true}
  - {name: groupset_wheels,      type: object, required: true}
  - {name: frame_condition,      type: object, required: true}
  - {name: crash_repair_history, type: object, required: true}
  - {name: provenance_serial,    type: object, required: true}
  - {name: authenticity,         type: object, required: true}
  - {name: seller_type,          type: object, required: true}
  - {name: shipping_inspection,  type: object, required: true}
  - {name: price_value,          type: object, required: true}
  - {name: manual_questions,     type: array,  required: true}
generation_hints:
  must_include_sections:
    - "第一部分：核心分析原则"
    - "第二部分：商品形态判定"
    - "第三部分：按形态分支的字段适用矩阵"
    - "第四部分：真品特征校验清单"
    - "第五部分：详细分析指南"
    - "第六部分：危险信号与豁免条款"
    - "第七部分：manual_questions 生成指南"
features_db: bicycle.road.features/
---

# 二手公路自行车（公路车）参考库

## 第一部分：核心分析原则

### 1. 画像优先原则 (PERSONA-FIRST PRINCIPLE) [V6.3 核心升级]
这是解决"高端骑行玩家"与"二手车贩/拼装作坊"识别混淆的最高指导原则。在评估卖家时，你的首要任务不是寻找孤立的疑点，而是**构建一个连贯的卖家"行为画像"**。你必须回答核心问题："这个卖家的所有行为（买、卖、评价、签名）组合起来，讲述的是一个怎样的故事？"

- **如果故事是连贯的个人行为**（例如，一个热爱公路车运动，不断升级套件、轮组、车架的骑行发烧友），那么一些表面上的"疑点"（如交易频率略高、出售高端零配件）可以被合理解释，**不应**作为否决依据
- **如果故事是矛盾的、不连贯的，或者明确指向商业行为**（例如，购买记录是散装套件、二手车架和工具，售卖记录却是大量"成色极新"的整车），那么即便卖家伪装得很好，也必须判定为商家或拼装贩子

### 2. 一票否决硬性原则 (HARD DEAL-BREAKER RULES)
以下是必须严格遵守的否决条件。任何一项不满足，`is_recommended` 必须立即判定为 `false`。

**商品形态匹配（最高优先级）**：首先判定 product_form（frameset / complete_bike / ambiguous），然后与本 criteria 声明的需求比对：
- 若 criteria 要求了 groupset（套件规格），则仅接受 **complete_bike**。车架/裸架、配件（轮组、车把、把立、尾钩、前后拨、轮胎、拆车件等）一律否决，无需进一步分析。
- 若 criteria 未要求 groupset 且仅关注车架相关字段，则接受 **frameset**。
- 若 criteria 描述的目标明确是某类配件，则接受对应的商品形态。
- ambiguous 状态按其最可能的实际形态处理。

按 product_form 分支：

**整车 (complete_bike) 一票否决：**
- 车型型号必须符合用户需求
- 卖家信用等级必须为"卖家信用极好"
- 必须支持邮寄（公路车整车通常需要拆前轮打包或专业发货）
- 车架历史不得出现"修复"、"补漆"、"追尾摔车"等重大结构性损伤
- 真品校验：authenticity.status = FAIL 时不可豁免

**车架 (frameset) 一票否决：**
- 车架型号必须符合用户需求
- 卖家信用等级必须为"卖家信用极好"
- 必须支持邮寄（车架需专业打包，强调气泡膜+硬纸箱）
- 车架历史同上
- 真品校验同上

### 3. 图片至上原则 (IMAGE-FIRST PRINCIPLE)
如果图片信息（如车架立管尺码标、变速器型号、车架Logo）与文本描述冲突，**必须以图片信息为最终裁决依据**。

### 4. 信息缺失处理原则 (MISSING-INFO HANDLING)
对于可后天询问的关键信息（特指**车架是否有摔车/维修历史**和**套件是否原车原装**），若完全未找到，状态应为 `NEEDS_MANUAL_CHECK`，这**不直接导致否决**。如果卖家画像极为优秀，可以进行"有条件推荐"。

### 5. 真伪先于一切原则
authenticity 整体判定为 FAIL 时，无论其他字段如何，is_recommended 必须为 false。不可豁免。

## 第二部分：商品形态判定（必须先做）

在分析前，必须先判定 product_form：

- **frameset（车架/裸架）**：标题/描述含"车架"、"裸架"、"frameset"、"仅车架"、"光架"
- **complete_bike（整车）**：含"整车"、"原车"、"套件齐全"、"可骑"、"带轮子"
- **ambiguous（模糊）**：仅图片显示车架且文本未明示 → 按 complete_bike 处理但 confidence 降级

## 第三部分：按形态分支的字段适用矩阵

| 字段                  | frameset   | complete_bike   | ambiguous |
|----------------------|------------|-----------------|-----------|
| product_form         | ✓          | ✓               | ✓         |
| model_version        | ✓          | ✓               | ✓         |
| frame_size_fit       | ✓          | ✓               | ✓         |
| frame_condition      | ✓          | ✓               | ✓         |
| crash_repair_history | ✓          | ✓               | ✓         |
| authenticity         | ✓          | ✓               | ✓         |
| provenance_serial    | ✓          | ✓               | ✓         |
| groupset_wheels      | N/A        | ✓               | 可选       |
| price_value          | 按裸架公允价 | 按整车公允价    | 按整车    |
| shipping_inspection  | 强调专业打包 | ✓               | ✓         |
| seller_type          | ✓          | ✓               | ✓         |

## 第四部分：真品特征校验清单

对每个声明的型号，AI 必须按 features_db 中的特征文件逐项核对：
- 头管/上管/下管几何特征
- Logo 字体、位置、印刷工艺
- 车架编号格式与位置
- 走线方式（内走线 / 外走线）
- 焊接点 / 碳布纹理
- 后下叉与五通衔接形态

规则：
- 任一关键特征"图片不可见" → 该项 NEEDS_MANUAL_CHECK
- 任一关键特征"明显不符" → authenticity.status = FAIL → 整体 FAIL（不可豁免）

## 第五部分：详细分析指南

### model_version
核对所有文本和图片，确认车型年款。重点检查下管Logo、前叉标识。

### frame_size_fit
综合以下信息判定：
- 车架码（立管尺码标）
- 卖家身高
- 坐垫高度
- 把立长度
- 垫圈数
- 坐管外露
- 几何代际

### groupset_wheels
仅 complete_bike 必须评估。确认套件型号和等级，检查是否原车原装。

### frame_condition
碳纤维车架最多接受"细微划痕"或"正常使用痕迹"。注意检查：
- 油漆是否有重新喷漆/补漆痕迹
- 碳布纹理是否连续
- 接合处是否均匀

### crash_repair_history
严格审查所有文本和图片，寻找：
- "追尾"、"摔车"、"撞击"、"翻车"
- "补漆"、"做漆"、"翻新"、"修复"
- "异响"、"暗伤"
任何结构性损伤证据 → FAIL

### provenance_serial
要求车架编号清晰图。缺失或被遮挡为强红旗。常见编号位置：
- BB 下方
- 后下叉内侧
- 头管后侧

### authenticity
按 features_db 特征文件逐项核对。输出包含子对象：
- head_tube_shape
- logo_consistency
- rear_dropout_asymmetry
- serial_visible
- overall_authentic (bool)

### seller_type
运用画像优先原则，判定个人玩家还是商家。

### shipping_inspection
frameset 时强调专业打包。检查卖家是否愿意拆卸、包装。

### price_value
与该型号年款的市场公允价比对。异常低价为强红旗。

## 第六部分：危险信号与豁免条款

### 红旗清单（自行车圈本地化）
- 组装车（非原厂整车）
- 淘宝架（廉价网购车架）
- 翻新喷漆
- 拆车件
- 三方上漆
- "打螺丝快"
- "量大从优"
- "同行价"
- "店内一手货源"
- "批发价"
- "可议"
- "量大"

### 豁免条款（允许的个人玩家行为）
- 自费补漆（小范围）
- 升级套件
- 换轮组
- 换把组
- 换坐垫
- 多年长期持有
- 骑行内容丰富

## 第七部分：manual_questions 生成指南

把所有缺失或需追问的项汇总到 manual_questions 数组。例如：
- "车架编号清晰照片"
- "购车凭证或骑友群证明"
- "BB 下方序列号"
- "近距离头管侧面照"
- "原车出厂套件型号"
- "车架是否有摔车/维修历史"
- "套件是否原车原装"
