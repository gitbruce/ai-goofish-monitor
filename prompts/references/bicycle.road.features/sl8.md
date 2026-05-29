# Specialized Tarmac SL8 真品特征

## 关键识别点（按可靠性降序）
1. 头管形状：SL8 头管前缘为非对称 aero cutout（区别于 SL7 平直前缘）
2. 下管 logo：标准 "TARMAC SL8" 印刷，居中略偏后
3. 后下叉：左侧短下叉（DropSeatStay），与 SL7 对称下叉不同
4. 走线：全内走线进入头管，Roval 把组一体化
5. 车架编号：BB 下方，格式 "WSBC" 或 "SBCU" 开头 + 8 位
6. 坐管夹：内嵌式，无外露夹环

## 常见伪冒形态
- 改色喷漆 SL7 车架贴 SL8 logo（下叉对称即漏馅）
- 廉价无标碳架喷涂 Specialized logo（头管形状对不上）
- S-Works SL8 涂掉 S-Works 字样冒充 SL8（重量 / 车架编号可查）

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
