# Giant Propel Advanced SL 真品特征

## 关键识别点（按可靠性降序）
1. 头管形状：Propel SL 一体式头管/前叉组合，前叉肩部为截面积造型（区别于 Advanced Pro 可拆前叉）
2. 下管 logo：标准 "PROPEL ADVANCED SL" 印刷，GIANT 品牌标位于下管前段
3. 后下叉：非对称后下叉设计，左侧明显更粗壮
4. 走线：全内走线，线管从把立下方进入头管
5. 车架编号：后下叉内侧右侧，格式 "GUxxxxx" 或 "Gxxxxxxxxx"
6. 坐管：Propel SL 专用一体式座杆（非圆管），与车架配套

## 常见伪冒形态
- Advanced Pro 级别（可拆前叉）冒充 SL 级别（一体式头管）
- 廉价 Giant OCR / TCR 改色喷涂 Propel SL logo（头管形状、后下叉比例不对）
- 翻新车架重新贴纸（logo 印刷精度不足、字体模糊）

## AI 必须输出（authenticity 子对象）
```json
{
  "head_tube_shape":       {"observed": "...", "matches_genuine": true, "evidence_image": "..."},
  "logo_consistency":      {"observed": "...", "matches_genuine": true, "evidence_image": "..."},
  "rear_dropout_asymmetry":{"observed": "...", "matches_genuine": true, "evidence_image": "..."},
  "serial_visible":        {"observed": "...", "matches_genuine": true, "evidence_image": "..."},
  "overall_authentic":     true
}
```
