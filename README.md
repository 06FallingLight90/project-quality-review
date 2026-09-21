# project-quality-review

从软件工程与架构视角对整个项目做质量体检的 Agent Skill：发现结构性问题并给出可落地的改进方案，输出 A/B/C/D 分级评级报告，不是逐行 code review。

## 仓库结构

```
.
├── README.md
└── skills/
    └── project-quality-review/     # 技能本体
        ├── SKILL.md                # 三步工作流（项目画像 → 分维度审查 → 汇总报告）
        ├── references/             # 七个维度的审查清单
        │   ├── architecture.md     # 架构设计（分层、边界、模式、抽象）
        │   ├── requirements.md     # 需求实现度（功能/非功能声明 vs 实现证据）
        │   ├── quality-attributes.md  # 内外部质量指标、场景六要素、效用树
        │   ├── code-smells.md      # 代码坏味道与架构坏味道
        │   ├── structure.md        # 目录结构
        │   ├── documentation.md    # 文档化（双向一致性）
        │   ├── metrics-evolution.md # 度量解读、架构腐蚀、重构策略
        │   └── evaluation.md       # ATAM/SAAM 轻量评估方法
        ├── assets/
        │   └── report-template.md  # 体检报告模板
        └── scripts/
            ├── mechanical_checks.py   # 超大文件、TODO、深嵌套目录
            └── dependency_metrics.py  # 依赖环、扇入扇出（Python/JS-TS）
```

## 审查维度

架构设计、需求实现度、质量属性（性能/可用性/可维护性等内外部指标）、代码坏味道与技术债、目录结构、文档化、度量与演化。深度评估支持 ATAM/SAAM 轻量流程（质量效用树、敏感点/权衡点/风险决策）。

## 安装到 Trae 全局技能

以 junction 链接接入，实时同步本仓库改动：

```powershell
New-Item -ItemType Junction -Path "$env:USERPROFILE\.trae-cn\skills\project-quality-review" -Target "<本仓库路径>\skills\project-quality-review"
```

## 触发场景

- 审查整个项目质量、架构评审、项目体检
- 评估质量属性、需求实现度、盘点技术债
- 检查目录结构或文档完整性

不用于单个 diff / commit / PR 的审查（见 pr-review 类技能）。
