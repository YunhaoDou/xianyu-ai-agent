# Contributing to xianyu-ai-agent

首先，感谢你愿意为这个项目做贡献！🎉

## 贡献流程

### 1. 报告 Bug

在 [Issues](https://github.com/YunhaoDou/xianyu-ai-agent/issues/new?labels=bug&template=bug_report.md) 提交，请包含：

- 清晰的问题描述
- 复现步骤
- 期望行为 vs 实际行为
- 运行环境（Python 版本、操作系统）
- 相关日志

### 2. 提交 Feature Request

在 [Issues](https://github.com/YunhaoDou/xianyu-ai-agent/issues/new?labels=enhancement&template=feature_request.md) 提交，请包含：

- 特性描述
- 使用场景
- 预期效果

### 3. 提交 PR

```bash
# Fork 并克隆
git clone https://github.com/你的用户名/xianyu-ai-agent.git
cd xianyu-ai-agent

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 创建功能分支
git checkout -b feat/your-feature-name

# 写代码 + 写测试
# 确保所有测试通过
pytest tests/ -v

# Commit（遵循 Conventional Commits）
git commit -m "feat: add your feature"

# Push 并创建 PR
git push origin feat/your-feature-name
```

## 代码规范

- **Python**: 3.10+，类型注解优先
- **格式**: 遵循 PEP 8，推荐使用 `ruff`
- **测试**: 新功能必须附带测试，覆盖率不低于 90%
- **Commit**: 遵循 [Conventional Commits](https://www.conventionalcommits.org/)
  - `feat:` 新功能
  - `fix:` Bug 修复
  - `docs:` 文档
  - `test:` 测试
  - `refactor:` 重构
  - `style:` 代码格式
  - `chore:` 构建/工具

## PR 审查标准

- [ ] 所有 CI 检查通过
- [ ] 新增代码有对应测试
- [ ] 代码风格一致
- [ ] 文档已更新（如有必要）
- [ ] 无破坏性变更（或已说明迁移路径）

---

**再次感谢你的贡献！🌟**
