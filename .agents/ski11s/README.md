# Skills Registry

项目级技能目录固定为：`.agents/ski11s/`（`ski11s` 为仓库约定命名）。

## 目录规范
- 每个技能必须是独立子目录：`.agents/ski11s/<skill-id>/`
- 必需文件：
  - `skill.yaml`
  - `README.md`
- 可选文件：
  - `install.sh`（存在时需可执行）
  - `use.md`

## 推荐结构
```text
.agents/ski11s/
  <skill-id>/
    skill.yaml
    README.md
    install.sh   # optional
    use.md       # optional
```

## skill.yaml 最低字段
- `name`
- `description`
- `version`

## 约束说明
- 技能发现仅基于 `.agents/ski11s/` 一级子目录。
- 仅含 `skill.yaml` 的子目录会被识别为有效技能。
- 本仓库 CI 会校验上述结构约束。
