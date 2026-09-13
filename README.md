# 灵感屿 · Sparkspace

先记下一句话，再沿着一个问题慢慢展开。灵感屿是一款个人思考工作台：按主题保存笔记，在主问题下面整理分支，把选中的内容交给 AI 继续完善。

支持独立桌面窗口、可置顶的一行速记栏、局域网手机配对、SQLite 保存、回收站与备份。前端使用原生 HTML/CSS/JavaScript，后端使用 Python 标准库，无需 npm 安装或云数据库。

## 启动

Windows [下载整个项目](https://github.com/pt-chon/sparkspace/archive/refs/heads/main.zip)并解压后，双击 **`灵感屿.exe`** 打开工作台。运行 `创建桌面入口.ps1` 可以生成主窗口与悬浮速记两个桌面快捷方式，速记栏按 **Ctrl + Enter** 保存，菜单里切换置顶。

`.exe` 是无控制台的 Windows 启动器，复用同目录的程序文件，不能单独移走。它仍需要电脑已安装 Python（含 Tkinter）和 Google Chrome；本机验证版本为 Python 3.14。也可从源码启动：

```powershell
python launch.pyw
python launch.pyw --quick
```

第一条打开完整工作台；第二条打开悬浮速记。重新编译启动器用 `powershell -ExecutionPolicy Bypass -File build-exe.ps1`，需要 Windows 自带的 .NET Framework 编译器。

仅启动网页服务，也可用于其他系统：

```sh
python server.py --host 0.0.0.0 --port 18478 --data-dir user-data
```

电脑浏览器打开 `http://127.0.0.1:18478`。手机与电脑连同一 Wi-Fi，在电脑的「连接手机」里生成配对码。防火墙需允许 Python 的 18478 端口用于私有网络。关闭窗口后服务仍运行，电脑关机或休眠时手机无法访问。

## 记录与 AI

- 每个主问题是一组，分支在组内展开；进入「只看这个问题」专注处理。
- 选中多条记录后可以导出、调用 AI 或删除。删除可连同后代一起回收，也可只删除所选并保留后代；分支可提为独立问题。
- AI 可处理整个主题、单条灵感或选中的一组，选择是否包含后代；支持默认模型与单次模型、默认提示词与单次要求。
- 本地 Codex 使用已登录的 CLI；兼容 API 使用服务商提供的地址、模型和 Key。模型列表仅供选择，是否可调用由账号权限与服务商决定。
- AI 先生成建议，采纳后保存为新分支，原始笔记保留。自动整理默认关闭，开启后会使用所选服务的额度。
- 示例主题涵盖世界书、角色卡、量化研究和其他创作场景。它们是演示材料，不是已验证的研究结论。

Windows API Key 使用当前用户的 DPAPI 加密；其他系统可通过 `SPARKSPACE_AI_API_KEY` 环境变量提供。Codex 在电脑上启动，但通常调用在线模型。此版本面向个人可信局域网；跨网可使用私人 VPN，未配置公网登录、HTTPS 或云同步。

## 数据与验证

个人笔记、配对会话、AI 配置和历史都在 `user-data/`，不进入 Git。完整备份可在「数据与设备」下载，恢复前会保留快照；跨设备编辑冲突会提示处理。多设备同步使用同一台电脑上的数据库。

```sh
node test_core.mjs
python test_server.py
python test_ai.py
python test_desktop.py
```

Windows `.exe` 检查用 `powershell -ExecutionPolicy Bypass -File test_exe.ps1`；桌面原生窗口检查用 `python test_desktop.py --ui`；`python test_ai.py --live` 会实际调用已登录 Codex，可能消耗额度，普通测试不进行真实模型生成。

更多操作见 [使用说明](使用说明.md)。此仓库只包含应用源码与虚构示例，不含个人笔记或凭据。

## 许可证

采用 [MIT](LICENSE) 许可证，版权归 pt-chon。分发源码或程序时请保留许可证与版权声明。
