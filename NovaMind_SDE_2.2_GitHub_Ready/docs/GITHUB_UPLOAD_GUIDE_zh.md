# NovaMind SDE 2.2：GitHub 上传指南（中文）

此 ZIP 已整理为可以发布的 GitHub 仓库内容。**请先解压 ZIP，再上传里面的文件和目录；不要只把 ZIP 文件本身上传到仓库。**

## 上传前说明

- 项目建议仓库名称：`novamind-ai-marketing-backend`
- 建议仓库描述：`Reliable AI marketing automation backend built with FastAPI, PostgreSQL, Celery, Redis, SQLAlchemy, and Alembic.`
- 建议 Topics：`python`, `fastapi`, `backend`, `postgresql`, `celery`, `redis`, `sqlalchemy`, `distributed-systems`, `software-engineering`, `ai-integration`
- 默认可以选 **Public** 作为作品集，但请自行确认源码版权和公开权限。
- **不要提交真实 `.env`、API Key、联系人数据、私有数据库、学校/公司的内部资料或运行日志。**
- 本公开版只保留 `data/sample_contacts.csv` 的 `@example.test` 模拟邮箱，已移除原始联系人样本与历史代码备份。
- 本仓库目前**未附加开源许可证**：默认不授予他人任意复制、修改、再发布的开源许可。若希望开源，请在 GitHub 中由权利人自行选择 MIT/Apache-2.0 等许可证。

## 方法 A：Git 命令行上传（推荐，保留隐藏配置文件）

1. 登录 [GitHub](https://github.com/new)，创建名称为 `novamind-ai-marketing-backend` 的空仓库。**不要勾选** Initialize with README / .gitignore / License，因为这些文件已经在项目中。
2. 将下载的 ZIP 解压到一个本地文件夹，例如 `novamind-ai-marketing-backend`。确认文件夹根目录直接有 `README.md`、`app/`、`.gitignore`、`.github/`。
3. 在该目录打开 Terminal（macOS/Linux）或 Git Bash（Windows），执行：

```bash
git init
git branch -M main
git add .
git status
git commit -m "Initial commit: NovaMind SDE 2.2 backend"
git remote add origin https://github.com/YOUR_USERNAME/novamind-ai-marketing-backend.git
git push -u origin main
```

将 `YOUR_USERNAME` 替换为你的 GitHub 用户名。若 Git 提示没有提交者信息，先运行 `git config --global user.name "Your Name"` 与 `git config --global user.email "your-github-email@example.com"`。实际认证建议使用浏览器登录、Git Credential Manager、SSH 或 GitHub CLI，而不是账户密码。

4. 刷新仓库首页，确认 `README.md`、`app/`、`tests/`、`alembic/` 和 `.github/workflows/ci.yml` 都出现。
5. 打开 **Actions**，观察 CI；首次构建可能需要调整环境依赖，请以仓库实际 CI 结果为准，不要把本地测试当成远程 CI 通过。

## 方法 B：GitHub 网页上传（不安装 Git）

1. 在 GitHub 创建一个空仓库，名称同上。
2. 打开仓库，选择 **Add file → Upload files**；若仓库为空，也可以选择初始页面的 **uploading an existing file**。
3. **先解压 ZIP**。将解压目录里面的全部文件与子文件夹拖入上传页面，不能只拖 ZIP。确保没有把外层文件夹作为唯一的顶层目录。
4. 输入 Commit message：`Initial commit: NovaMind SDE 2.2 backend`，然后提交。
5. 如果网页或系统隐藏了 `.gitignore`、`.github/` 等以点开头的文件，请在 Finder 中按 **Cmd + Shift + .** 显示隐藏文件，或使用方法 A。网页上传对 `.gitattributes` 行尾处理有限，完整上传更推荐 Git。
6. GitHub 文档说明浏览器单个文件最大 25 MiB、一次最多 100 个文件。本包已做精简，大小与数量在该限额内。

## 上传后建议

- 在 GitHub 的 **About** 编辑描述、Topics，Website 可留空。
- 检查 Actions 流水线和 README 跳转链接；有了真实 URL 再添加 CI 状态徽章。
- 不要将项目描述为“已上线的生产营销平台”。本版本是经过本地测试的工程参考实现，不发送真实营销邮件；PostgreSQL/Celery 多进程故障测试和云部署还未完成。
- 如需持续维护，可增加 Issues、Milestones 以及独立 Feature 分支。

## 本地快速验证

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
python -m pytest -q
python -m app.cli demo
uvicorn app.main:app --reload
```

Windows PowerShell：`python -m venv .venv`、`.venv\Scripts\Activate.ps1`，文件复制命令使用 `Copy-Item .env.example .env`。

## 常见错误

- **上传 ZIP 后只显示一个 ZIP：** GitHub 不会将它自动展开成源码仓库，请解压后上传内容。
- **`git remote origin already exists`：** 用 `git remote -v` 检查已有地址，必要时用 `git remote set-url origin https://github.com/YOUR_USERNAME/novamind-ai-marketing-backend.git`。
- **`failed to push some refs`：** 确保新仓库未初始化另一份 README；若已初始化，应先安全合并历史，不要盲目使用 `--force`。
- **提示 secret scanning：** 不应绕过；检查是否误把真实密钥加入文件，轮换泄露的 Token，并删除敏感文件及 Git 历史中的相关内容。
- **CI 报错：** 优先阅读 Actions 日志定位依赖、Lint、Migration 或测试差异，不要在 README 中声称远程 CI 已通过。

官方参考：[GitHub 添加文件](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)；[已有本地代码上传 GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)。
