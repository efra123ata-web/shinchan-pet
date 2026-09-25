# 蜡笔小新桌宠 🖍️

一个跑在 Windows 桌面上的蜡笔小新桌宠：会走动、能拖拽、支持 34 种动画切换、和小新 AI 聊天，还能查 API 余额。

> 本项目基于 [Xiao-MengFu/Crayon_Shin-chan_Desktop_Pet](https://github.com/Xiao-MengFu/Crayon_Shin-chan_Desktop_Pet)（MIT）二次开发，
> 新增了 **DeepSeek 余额查询**、素材目录重构、以及配置模板化。

## 功能

- **34 种动画**：屁股舞、动感光波、跳芭蕾、吹萨克斯、抱小白、火箭飞天、脚踏车……托盘菜单「切换」随意换
- **拖动 + 边缘互动**：拖到屏幕边缘松手，开启「移动开关」后会有飞天/跑回来等效果
- **AI 聊天**：托盘「聊天」唤起对话框，小新会用动画角色的语气和你唠（走 OpenAI 兼容接口）
- **余额查询** 🆕：托盘「查询余额」弹窗显示当前账户余额；鼠标悬停托盘图标也会显示余额（每 10 分钟自动刷新）
- **BGM**：小新主题曲，托盘可开关 + 音量调节

## 快速开始

### 1. 环境要求

- Windows
- Python 3.10+

### 2. 安装

```bash
git clone <your-repo-url>
cd shinchan-pet

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置

复制 `.env.example` 为 `.env`，填入你的配置：

```env
BASE_URL=https://api.deepseek.com/v1
API_KEY=sk-你的key
MODEL=deepseek-flash
```

> 任何 **OpenAI 兼容** 的服务都行（DeepSeek / 智谱 / OpenAI / 本地 Ollama…）。

### 4. 准备素材

⚠️ **本仓库不包含图片和音频素材**（见下方「素材说明」）。

请自备素材，按以下结构放好：

```
assets/
├── sprites/          # 每个动画一个文件夹，里面放 0.png 1.png 2.png ...
│   ├── 01 招手/
│   ├── 02 跳舞/
│   └── ...
└── audio/
    ├── 蜡笔小新INTRO.wav
    └── 蜡笔小新BGM.wav
```

动画文件夹名就是托盘菜单里显示的名字。

### 5. 运行

```bash
python pet.py
```

小新会出现在屏幕右下角，设置菜单在**系统托盘**图标上（右键）。

## 素材说明 ⚠️

**本仓库不含任何图片/音频素材**，原因：蜡笔小新是受版权保护的动漫形象（©臼井儀人 / 双葉社），公开传播其素材属于侵权行为。

因此：
- 仓库只开源**代码**（MIT）
- 素材请自行准备：自己绘制、使用免费可商用素材，或用于个人学习

代码兼容任何 PNG 序列 + WAV 音频，换成你自己的原创形象就能变成一个全新的桌宠 —— 改个文件夹和主角设定即可。

## 项目结构

```
shinchan-pet/
├── pet.py              # 主程序（桌宠窗口 + 托盘 + 聊天 + 余额）
├── config.py           # 读取 .env 配置
├── requirements.txt
├── .env.example        # 配置模板
├── 蜡笔小新设定.md      # 聊天用的角色设定
└── assets/             # 素材（gitignore，需自备）
    ├── sprites/
    └── audio/
```

## 致谢

- 原始项目：[Xiao-MengFu/Crayon_Shin-chan_Desktop_Pet](https://github.com/Xiao-MengFu/Crayon_Shin-chan_Desktop_Pet)（MIT）
- 原始灵感：[走神的阿圆](https://space.bilibili.com/24657764) 的桌面宠物教程

## License

MIT（代码部分）
