"""backend/h6_fixtures —— V2.1.0 H6（PLAN §18.2）可移交确定性虚构测试资产。

- 全部姓名/组织/联系方式/经历/JD/事实均为虚构，不含真实个人信息、API Key 或本机绝对路径；
- resume_doc.json / jd.txt / identity_samples.json / preview_anchors.json 为冻结 fixture；
- gen_fixtures.py 提供字节级可复现的 PDF（reportlab invariant=1 两页）与 DOCX
  （python-docx + 确定性重打包）生成器；fixture_hashes.json 记录冻结时 SHA-256 供审计对照。

本包只被专项测试资产（backend/_v21_h6_matrix.py、backend/_v21_h6_stub.py 与
scripts/precheck.py 的 H6 阻断步骤）引用；不进入正式应用路由、普通构建或生产包。
"""
