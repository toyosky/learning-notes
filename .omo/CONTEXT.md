# Project Context

## Remote Repositories
- **Primary**: GitHub (SSH) — `git@github.com:toyosky/learning-notes.git`
- **Mirror**: Gitee (HTTPS) — `https://gitee.com/yin_river/learning-notes.git`
- Git User: chenyou <1291929850@qq.com>
- Branch: main

## Authentication
- GitHub: SSH key (`~/.ssh/github_ed25519`)
- Gitee: Credential store (`~/.git-credentials`)

## Workflow
```bash
# 提交笔记（默认推送到 GitHub）
git add -A && git commit -m "描述修改内容"
git push github main

# 同时同步到 Gitee 备份
git push origin main

# 首次在本地电脑克隆
git clone git@github.com:toyosky/learning-notes.git
```

## Notes
- This vault is an Obsidian notebook covering AI/ML and quantitative trading
- Do NOT commit large binary files (>50 MB) to the repo
- `.obsidian/` and `.hermes/` directories are part of the vault
