# DeepSeek 余额小鲸鱼挂件 for Windows（DeepSeek Balance Whale Widget for Windows）

![DeepSeek 余额小鲸鱼挂件 for Windows](doc/DSB.jfif)

[DSH 小鲸鱼余额挂件](https://github.com/MeteorNOX/DeepSeek-Balance-Whale-Widget) 项目的 Windows 平台实现（使用 Python 重写）。

Windows 悬浮窗余额挂件：小鲸鱼气泡图 + DeepSeek API 余额 + 峰谷提示。

## 特性

- 💰 **余额**：点击鲸鱼显示**余额**与**峰谷提示**；余额变化时数字滚动动画；10s内自动沿用最近余额、托盘内手动刷新；气泡总显示 5 秒自动收起
- 📊 **今日已用**：鲸鱼娘每次观测余额后用余额差值自动记账（`status.json`，跨天自动归零归档）
- 🖱️ **动效**：拖拽 + 四边吸附
  - 🔄 左半屏时整体**水平镜像翻转**（文字同步反向、带动画）
  - 🧸 **按压 Q 弹**玩偶效果（按压时底部坐标不变）
- 🔊 **音效**：按压/松手音效（默认关闭，托盘内开关）
- 📌 **Windows 托盘图标**：左键隐藏；右键常用配置菜单（此处配置存放于`status.json`）
- 📝 **配置文件**：缺失自动释放；APIKEY、大小调整、音量调节、位置记忆、峰谷提示文案（默认 / 梁文峰谷 / !?强强?!）、随机台词
- 💬 **随机台词**：**点击气泡**切换随机台词段（加权随机）；右键鲸鱼显示 GIF 动图
- 📦 **单文件**：即用即删，无残留；运行后同目录下会自动生成配置和状态文件（`config.ini` 和 `status.json`）


### 预览图

<img src="doc/preview.png" alt="Preview" width="75%">

## 使用引导 

> [!IMPORTANT]
> - 首次运行后，在出现的配置文件内填入 `API_KEY` 并保存<br>
> - 运行后程序出现在**右下角托盘**，右键托盘图标可进行 `退出` 等常用操作


## 安装

### 方法 1. Github Releases

[下载最新版](https://github.com/MrBocchi/DeepSeek-Balance-Whale-Widget-For-Windows/releases/latest/download/DSBWhale-win.exe)

### 方法 2. 自行编译

> 环境要求：Windows + Python（推荐 3.14，非必要）

安装依赖
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

运行测试（可选）
```
python whale_widget.py
```

编译 exe
```
python -m PyInstaller --noconfirm --clean --onefile --windowed --name DSBWhale-win --icon assets\DSniang1.png --add-data "assets;assets" whale_widget.py
```

可执行文件会出现在 `dist` 子文件夹


## 开机自启

将可执行文件 `DSBWhale-win.exe` 放置于一个单独的不常用文件夹，手动**创建快捷方式**至 `%AppData%\Microsoft\Windows\Start Menu\Programs\Startup`；**注意不是移动**。

## 卸载

删除 `DSBWhale-win.exe` 以及同目录下的 `config.ini` 和 `status.json`（如果有）即可；本程序没有其他残留。

## 许可证

本项目基于 **MIT License** 开源，详见 [LICENSE](LICENSE)。