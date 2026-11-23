# 凭据处理说明

本分支由自动化流程推送，**所有凭据已移除**：

- `CREDS.md` 与 `.creds.json` 未包含在仓库中（前者本来就在 `.gitignore` 里）。
- `code/` 下 13 个历史脚本里硬编码的密码已替换为 `REDACTED_*` 占位符。
  它们现在无法直接运行，需要自行以环境变量注入：

```bash
export AUTODL_32922_PASSWORD=...
export AUTODL_26853_PASSWORD=...
export LAB_PASSWORD=...
```

实验室服务器与 AutoDL 实例的访问方式见 `HANDOFF.md` §4（只写地址与路径，不含密码）。
