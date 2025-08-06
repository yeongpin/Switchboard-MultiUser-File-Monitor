# Switchboard MultiUser File Monitor

一个用于监控和管理Unreal Engine 5.6 Switchboard MultiUser临时文件的Python工具。

## 功能特性

- 🔍 **自动检测Switchboard配置**：自动识别当前使用的Switchboard配置文件
- 📁 **实时文件监控**：监控MultiUser会话的临时文件变化
- 📋 **会话列表显示**：显示所有活跃的MultiUser会话，包括会话ID、用户ID、修改时间等信息
- 🌳 **文件树浏览**：以树形结构显示会话中的所有文件
- ✅ **选择性复制**：可选择特定文件或文件类型进行复制
- 🚀 **批量操作**：支持批量复制多个会话的文件
- 📊 **进度追踪**：实时显示复制操作的进度
- 📝 **操作日志**：详细记录所有操作和错误信息
- 🔄 **可选Sandbox同步**：用户可选择是否启用Sandbox目录同步
- 🌐 **网络驱动器同步**：支持同步到多个网络驱动器位置
- 🎛️ **灵活的工作流**：支持仅复制到Content目录或完整的网络同步流程
- 🎬 **增强的Switchboard界面**：提供完整的Switchboard信息显示和快速启动功能
- 📊 **系统状态监控**：实时监控Switchboard进程和配置状态
- ⚡ **快速操作面板**：一键启动Switchboard、刷新信息、清理进程

## 安装要求

- Python 3.8+
- PySide6 6.5.0+
- Unreal Engine 5.6 (with Switchboard)

## 安装步骤

1. 克隆或下载这个项目到本地：
```bash
git clone <repository-url>
cd switchboard-multiuser-monitor
```

2. 安装依赖项：
```bash
pip install -r requirements.txt
```

## 使用方法

1. 启动应用程序：
```bash
python src/main.py
```

2. **Switchboard标签页**：
   - **信息标签**：显示Switchboard配置信息、可用配置、设备状态等
   - **快速操作标签**：一键启动完整Switchboard、刷新信息、清理进程
   - **状态监控标签**：实时监控Switchboard可用性、配置状态、进程状态
   - 支持自动刷新功能，每30秒自动更新信息

3. **MultiUser文件监控标签页**：
   - 应用程序将自动检测Switchboard配置
   - 如果检测到多个配置，可从下拉菜单选择
   - 应用会显示当前配置的项目信息
   - **配置切换时会自动清空旧的会话列表**，确保显示的是当前配置的会话

4. 监控MultiUser会话：
   - 当在UE中进行MultiUser协作时，应用会自动检测到新会话
   - 会话列表会显示：会话ID、用户ID、最后修改时间、文件数量、总大小
   - 会话按最后修改时间排序，最新的会话显示在顶部

5. 浏览和选择文件：
   - 选择一个会话后，右侧会显示该会话的文件树
   - 可以勾选要复制的文件
   - 支持按文件类型快速选择（UE资源、配置文件、源代码等）

6. 复制文件：
   - **单个会话**：双击会话或选中后点击"Copy Selected"
   - **多个会话**：点击"Copy All Sessions"进行批量复制
   - 选择目标目录（默认为项目的Content目录）
   - 配置复制选项（是否覆盖、文件过滤等）
   - **Sandbox同步选项**：勾选"Enable Sandbox sync"启用自动同步功能

7. 自动Sandbox同步（可选）：
   - 如果启用了"Enable Sandbox sync"选项：
     - 复制成功后，会先清除旧的Sandbox目录内容
     - 然后将文件复制到项目根目录的Sandbox文件夹
     - 应用程序内置了`sync_sandbox.bat`脚本，会自动执行同步
     - 同步脚本会将Sandbox内容同步到多个网络驱动器
     - 整个过程在复制对话框中显示详细日志
     - 脚本会临时复制到项目根目录执行，确保路径正确
   - 如果未启用，则只复制到Content目录，不执行网络同步

## 目录结构

```
src/
├── main.py                 # 应用程序入口点
├── core/                   # 核心功能模块
│   ├── config_detector.py  # Switchboard配置检测
│   ├── file_monitor.py     # 文件监控器
│   └── file_manager.py     # 文件管理器
├── ui/                     # 用户界面组件
│   ├── main_window.py      # 主窗口
│   ├── session_widget.py   # 会话列表组件
│   ├── file_tree_widget.py # 文件树组件
│   └── copy_dialog.py      # 复制对话框
├── external/               # 外部脚本
│   └── sync_sandbox.bat    # Sandbox同步脚本
└── utils/                  # 工具模块
    └── logger.py           # 日志工具
```

## 配置路径

应用程序会在以下位置查找Switchboard：

- `D:/UE_5.6/Engine/Plugins/VirtualProduction/Switchboard/Source/Switchboard`
- `C:/Program Files/Epic Games/UE_5.6/Engine/Plugins/VirtualProduction/Switchboard/Source/Switchboard`
- 当前目录及其父目录中的switchboard文件夹

MultiUser临时文件通常位于：
```
<EngineDir>/Programs/UnrealMultiUserSlateServer/Intermediate/MultiUser/
<SessionID>/<UserID>/Sandbox/Game/
```

## 使用场景

这个工具解决了以下问题：

1. **手动复制的繁琐**：在Switchboard MultiUser协作中，临时文件保存在中间目录，需要手动复制到项目Content目录

2. **需要关闭UE和Switchboard**：通常需要关闭UE和Switchboard才能访问临时文件

3. **文件定位困难**：MultiUser的临时文件路径包含复杂的UUID，难以手动定位

4. **批量操作不便**：当有多个会话时，需要逐个处理

## 注意事项

- 建议在复制文件前备份原有的Content目录
- 某些文件可能正在被UE使用，复制时可能失败
- 应用程序需要有读取Switchboard配置文件的权限
- 确保目标目录有足够的磁盘空间

## 故障排除

**Switchboard模块导入失败 ("No module named 'switchboard'")**
这是常见问题，通常发生在：
- Switchboard的Python模块无法访问
- Python环境与Switchboard不兼容

**自动解决方案：**
- 程序会自动切换到后备配置模式
- 在后备模式下，程序会直接扫描MultiUser目录
- 界面会显示"⚠️ Warning: Using fallback configuration"

**手动测试：**
```bash
python test_fallback.py
```

**无法检测到Switchboard配置**
- 检查Switchboard安装路径是否正确
- 确保有读取配置文件的权限
- 检查UE版本是否为5.6
- 如果Switchboard不可用，程序会自动使用后备模式

**文件监控不工作**
- 确保MultiUser服务正在运行
- 检查MultiUser工作目录路径
- 重启应用程序并重新检测配置
- 确认以下路径是否存在：
  - `D:/UE_5.6/Engine/Programs/UnrealMultiUserSlateServer/Intermediate/MultiUser`
  - `项目目录/Intermediate/Concert/MultiUser`

**复制操作失败**
- 检查目标目录是否存在且可写
- 确保没有文件正在被其他程序使用
- 查看日志了解具体错误信息

## 许可证

本项目仅供学习和个人使用。使用时请遵守Epic Games的相关许可协议。

## 贡献

欢迎提交问题报告和功能建议。在提交代码前，请确保：

1. 代码符合PEP 8规范
2. 添加适当的注释和文档字符串
3. 测试新功能是否正常工作

## 更新日志

[CHANGELOG.md](CHANGELOG.md)