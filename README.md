# Musicaldg 的个人网站

暖白与鼠尾草绿的个人博客。静态页面，无需安装依赖，适配手机与桌面。

网站：https://musicaldg.github.io/

## 文件管理

- `site.json`：显示名称、简介、GitHub 链接与网站地址。
- `templates/`：首页与公共页面结构，调整介绍请编辑这里。
- `assets/`：样式、图标与文章图片（建议 `assets/posts/文章名/`）。
- `content/posts/`：Markdown 文章源文件。
- `scripts/build.py`：生成首页、博客、RSS、站点地图和 404。
- `index.html`、`blog/` 等：生成结果，请勿直接编辑。
- `generated-files.json`：生成文件清单，用于移除撤回文章的旧页面。

不要提交密钥、账号令牌、私人草稿或备份文件。`draft: true` 仅防止文章显示在网页，公开仓库中的源文件仍然可见。

## 写一篇文章

新建 `content/posts/my-first-post.md`，使用以下格式：

```markdown
---
title: 文章标题
date: 2026-09-29
summary: 一句话简介。
draft: true
---

## 一个小标题

这里写正文，可用 **加粗**、*斜体*、`行内代码` 和 [链接](https://github.com/Musicaldg)。

- 一个要点
- 另一个要点
```

文件名使用小写英文、数字和连字符；发布后链接为 `/blog/my-first-post/`。
支持标题、段落、链接、图片、加粗、斜体、普通列表、引用、分隔线和三反引号代码块。暂不支持表格、嵌套列表、脚注及数学公式；需要时扩展构建器。原始 HTML 会转义。

确认内容后将 `draft` 改为 `false`。日期为展示日期，不支持定时发布。

## 本地预览

```sh
python3 scripts/build.py
python3 -m http.server 8000 --bind 127.0.0.1
```

打开 http://127.0.0.1:8000/ 。修改后重新构建并刷新。

## 发布

首次配置 Git 作者身份，并确保 GitHub 的 HTTPS 凭据已登录。

```sh
sh scripts/publish.sh "发布：文章标题"
```

脚本会检查 master 与远端是否一致，再构建、检查差异、提交和普通推送。若之前已有本地提交未推送，检查后直接 `git push origin master`。多人或多设备协作时，先保存本地修改并同步远端。不要强制推送。

GitHub Pages 应配置为 **Deploy from a branch → master → / (root)**，生成页面随提交发布。Actions 会校验构建结果与已提交页面一致。Pages 更新通常需要等待部署结束；以部署结果和线上页面为准。

## 旧版本恢复

替换前的仓库提交为 `0e5fff8`，旧内容仍在 Git 历史中。本机另有完整备份 `/tmp/personal-website-backups/Musicaldg-before-redesign-20260929.bundle`，临时目录可能被系统清理，长期恢复应使用 Git 历史。

撤销本次替换可对本次提交执行 `git revert <提交号>` 并推送；这会生成恢复提交，不覆盖历史。先保存当前未提交改动。
