# -*- coding: utf-8 -*-
"""DeepSeek 余额小鲸鱼挂件 —— Windows 桌面版（系统托盘 + 全局置顶悬浮窗）

本文件由原 DSH Web 插件 ``lib/index.js`` 逐步反推重写而成：

* 挂件本体（鲸鱼贴图 DSniang1.png + 思考气泡 + 文本）→ tkinter 无边框 / 置顶 /
  抠色透明的悬浮窗口，绘制逻辑按原 CSS 与 SVG 的相对坐标 1:1 折算；
* 原网页菜单（大小 / 音效 / 用量 / 峰谷 / 气泡 / 避让滚动条）→ 托盘右键菜单
  （余额 / 按下回弹 / 音效 / 隐藏 / 打开配置文件 / 关于 / 退出，带分隔线）+ config.ini；
* 余额接口、失败重试与 stale 兜底、15s 余额缓存、记账账本（余额差值累计今日
  已用）、峰谷时段判定、随机台词 / 权重 —— 按 ``lib/index.js`` 反推保留；
* 左键单击托盘 = 显示 / 隐藏悬浮窗；右键 = 实时弹出菜单
  （余额 / 按下回弹 / 音效 / 隐藏 / 打开配置文件 / 关于 / 退出）；
  “余额” = 立即实时查询；托盘（悬停）文本：加载中 ``余额：...`` → 完成后 ``余额：¥ 1.00``。

文件分工：
* ``config.ini``  用户配置（API_KEY / WIDGET_SCALE / SOUND_VOLUME / SAVE_POSITION /
  PEAK_MODE / 「随机台词」）：不存在时按 py 内置的 ``CONFIG_DEFAULT`` 自动生成；
  某一项缺失或写坏时退回内置默认值；API_KEY 为空也能正常运行
  （气泡里提示“API_KEY为空”，并在启动时自动用记事本打开本文件供填写）。
* ``status.json`` 运行期状态（音效开关 / 按下回弹开关 / 悬浮窗位置 / 记账账本）：
  不存在时自动创建。
* 打包单文件 exe：``pyinstaller --onefile --windowed`` + ``--add-data "assets;assets"``；
  可写文件（config.ini / status.json）生成在 exe 同目录，assets 从打包资源里读。

依赖：pystray、Pillow、requests（安装与运行见文件开头的说明块）。
"""

# ==========================================================================
# 安装与运行（在项目根目录执行）：
#
#   python -m venv .venv
#   .venv\Scripts\python.exe -m pip install pystray Pillow requests
#   .venv\Scripts\pythonw.exe whale_widget.py
#
# 使用说明：
#   * 运行后默认形态 = 有气泡 + 余额。
#   * 左键点击右下角「人物主体」：按「无气泡 → 余额 → 峰谷 → 隐藏」循环
#     （无气泡时显示一个必定是「余额」的气泡；已是「余额」气泡时切到「峰谷」；
#     其余情况一律隐藏）。
#   * 右键点击右下角「人物主体」：在「有气泡且必为 rua.gif」与「无气泡」之间切换。
#   * 点击左上角「气泡」（任意键）按固定顺序推进：
#     rua.gif → 余额 → 峰谷 → 之后一直在「随机台词」之间随机切换
#     （不会再回到 rua.gif / 余额 / 峰谷）。
#   * 「峰谷」气泡第三行是距下次峰谷切换的倒计时（⏳剩余HH:MM:SS，每秒刷新），
#     字号与原来一致，颜色跟随主文字（高峰红 / 空闲绿）。
#   * 任何鼠标操作都会播放音效（与气泡状态无关）：按下响 Ya1.mp3，松开后 Ya2.mp3
#     紧接在 Ya1 的尾音上（留 SOUND_CHAIN_OVERLAP_MS 的重叠，听感连贯）；
#     单击一定把两个音频都放出来，连续快速点击则打断并从头重播。
#     托盘右键菜单里的「音效」开关控制这套音效（默认关闭），
#     开启时会连响 Ya1+Ya2 作为提示；开关状态记忆在 status.json。
#   * 任何鼠标按下都会让整个挂件纵向“Q弹”收缩：按下即收缩并保持，松开后弹回
#     原高度（欠阻尼弹簧，带轻微过冲）；连续点击可随时打断上一段动画。
#     该效果可用托盘的「按下回弹」开关（位于「余额」之下、「音效」之上，
#     默认开启）；关闭时会立即回到原高度并停止后续缩放。
#   * 动画帧率跟随显示器刷新率：Q弹与翻转**共用一个帧循环**（同一帧推进两个
#     动画、只合成上屏一次），动画运行期间临时把系统定时器精度提到 1ms、
#     并按实测渲染耗时自适应帧间隔（60Hz 屏 ≈60fps、160Hz 屏 ≈150fps），
#     动画一结束立刻恢复原精度，不做常驻。
#   * 气泡到点自动关闭（BUBBLE_MS 可调）；上述任何点击都会重置这个倒计时。
#   * 悬浮窗全局置顶，按住可拖拽移动；窗口边缘距屏幕边缘小于 SNAP_DISTANCE
#     像素就会贴边吸附，并在吸附的同一瞬间按左右侧决定贴图方向（左半屏 → 镜像）。
#     换方向时整个挂件会做一次非线性的「翻转」动画（横向收到最窄再张开），
#     换向发生在最窄的 50% 处，所以气泡里的文字 / 动图全程都不会被镜像。
#   * 是否记忆悬浮窗位置由 config.ini 的 SAVE_POSITION 控制（默认 false，
#     每次启动都回到右下角）。
#   * 没有后台定时刷新，只在点击时实时获取；BALANCE_TTL_S 秒内的重复获取
#     直接显示缓存余额、不再发请求。
#   * 加载中的省略号只出现在托盘文本里；悬浮窗内「余额」区域显示“加载中...”，
#     「今日使用」区域整行不显示。
#   * 托盘菜单里还有：「打开配置文件」用**记事本**打开同目录的 config.ini
#     （没有时会先生成），保存或关掉窗口后配置**自动重载**；程序退出时会
#     自动关掉这个记事本窗口。
#   * 启动时 API_KEY 为空（首次使用）→ 自动打开一次 config.ini 供填写
#     （与「打开配置文件」同一套逻辑，不会重复生成配置文件）。
# ==========================================================================

from __future__ import annotations

import configparser
import ctypes
import datetime
import json
import math
import os
import queue
import random
import sys
import subprocess
import threading
import time
import webbrowser
from ctypes import wintypes

import requests
import tkinter as tk
from PIL import Image, ImageDraw, ImageFont, ImageTk

import pystray


def _log(msg) -> None:
    """安全日志：pythonw 下 sys.stdout/sys.stderr 为 None，print 会直接抛异常。"""
    try:
        stream = sys.stderr or sys.stdout
        if stream is None:
            return
        stream.write(str(msg) + "\n")
        stream.flush()
    except Exception:
        pass


# ==========================================================================
# ============================ 用户配置区 ==================================
# ==========================================================================
# 所有可调项都在同目录的 config.ini 里：
#   [common] API_KEY / WIDGET_SCALE / SOUND_VOLUME / SAVE_POSITION / PEAK_MODE
#   [lines]  「随机台词」各组的权重、样式、折行与候选文案
# 下面“配置读取”段会在启动时把它读进来；文件不存在会按内置的 CONFIG_DEFAULT
# 自动生成一份，文件缺失或某一项写坏时逐项退回内置默认值（API_KEY 为空也能运行）。
#
# 运行期状态（音效开关 / 按下回弹开关 / 悬浮窗位置 / 记账账本）统一放在同目录的 status.json。
# ==========================================================================


# ------------------------------- 路径 -------------------------------------
# 打包成单文件 exe（PyInstaller --onefile）后要区分两类目录：
#   * APP_DIR   ：可写文件（config.ini / status.json）放这里——exe 所在目录；
#   * BUNDLE_DIR：只读资源（assets）放这里——打包后是临时解包目录 sys._MEIPASS。
# 直接跑 py 时两者都是脚本所在目录。
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
    BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APP_DIR

SCRIPT_DIR = APP_DIR          # 兼容旧引用：脚本/exe 所在目录
ASSETS_DIR = os.path.join(BUNDLE_DIR, "assets")

# 悬浮窗贴图（assets 目录下的文件名，可选 DSniang1.png / DSniang02.png / DSH2.png）
WHALE_IMAGE_NAME = "DSniang1.png"
WHALE_IMAGE = os.path.join(ASSETS_DIR, WHALE_IMAGE_NAME)
# 气泡里的 rua 动图（对应 RUA_GIF_CANDIDATES[0]；缺失时自动降级为文字台词）
RUA_GIF = os.path.join(ASSETS_DIR, "rua.gif")
# 用户配置（不存在时会按 CONFIG_DEFAULT 自动生成）
CONFIG_INI = os.path.join(APP_DIR, "config.ini")
# 运行期状态：音效开关 / 按下回弹开关 / 悬浮窗位置 / 记账账本 全部放在这一个文件里
STATUS_FILE = os.path.join(APP_DIR, "status.json")

# 点击音效：鼠标按下播放 Ya1.mp3、松开播放 Ya2.mp3（悬浮窗上任意鼠标操作都会响）
#   统一走 Windows 自带的 MCI（winmm）——只有它支持调节响度；
#   两个音频各自使用独立的 MCI 别名，互不打断，快速连点也不会截断前一声；
#   MCI 完全不可用时才回退到 winsound（此时不保证响度生效）。
SOUND_PRESS_FILE = os.path.join(ASSETS_DIR, "Ya1.mp3")
SOUND_RELEASE_FILE = os.path.join(ASSETS_DIR, "Ya2.mp3")

# 中文字体（原文案均为中文，建议用微软雅黑）
FONT_REGULAR = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
# emoji 字体：微软雅黑没有 ⏳（U+23F3）这类字形，那个字符单独用它绘制
FONT_EMOJI = r"C:\Windows\Fonts\seguiemj.ttf"


# ------------------------------- 配置读取 ---------------------------------
# 内置的默认配置（纯文本，供 config.ini 不存在时原样释放出去）：
#   * 保留原有的空行与缩进，不用任何转义符，方便直接用记事本编辑；
#   * 同时也是“某一项在 config.ini 里缺失/写坏”时的逐项退路。
# ; 每一项都可以省略或留空（API_KEY 留空也能运行，只是气泡里提示“API_KEY为空”）。
CONFIG_DEFAULT = """; DeepSeek 余额小鲸鱼挂件 —— 配置文件（UTF-8）
; 修改后需要重启应用才会生效（从托盘内打开可以免重启）。
; 本文件由程序在缺失时自动生成；删掉它就会重新生成一份默认配置。

[common]
; DeepSeek API Key（必填）
; 若为空：启动时会自动打开一次本配置文件，方便直接填写
API_KEY = 

; 悬浮窗实际缩放比（取值范围 0.6 ~ 2.5）
WIDGET_SCALE = 1

; 点击音效的响度，0.0（静音）~ 1.0（原始音量），可用小数如 0.35。
; 右键托盘菜单里的「音效」可以整体开关（默认关闭）。
SOUND_VOLUME = 1.0

; 是否记忆悬浮窗位置（true：记住上次位置；false：每次启动都回到右下角默认位置）
SAVE_POSITION = false

; 「峰谷」文案模式（点击气泡在「峰谷」时显示的那一行）
;   default    = 空闲时段 / 高峰时段
;   liangwen   = 梁文谷 / 梁文峰
;   qiangqiang = !?谷谷?! / !?峰峰?!
; 其余任何值都按 default 处理；文字颜色不变（空闲绿、高峰红）
PEAK_MODE = default


[lines]
; 「随机台词」：点击气泡由「余额」推进到「峰谷」之后，会一直在这几组里随机抽。
; 每组格式：权重 | 样式 | 折行 | 候选台词1, 候选台词2, ...
;   权重：抽签的相对权重（数值越大越常出现，可以是小数）
;   样式：A = 小字标签（如“DeepSeek 余额”）
;         B = 大字（余额数字那种，粗体）
;         P = 时段色大字（峰谷那种，粗体）
;         C = 浅色小字（“今日已用”那种）
;   折行：true = 超出气泡宽度时自动折行；false = 不折行
;   候选台词：同一组内多条用英文逗号分隔；每次随机取一条
; 注意：注释必须独占一行，值里不要写分号。
line1 = 4 | B | false | 好模型... ↓, 好女孩...↓
line2 = 7 | A | true | 不知道用户有什么用，先赶走吧~, 我...我...我也要挣钱吗？, 我去吃饭啦，测完叫我, 压力一只蓝色大肥鱼？！, DeepSleep..., 坏了...用户彻底怒了！
line3 = 3 | A | true | 你目录里的dsh是什么...大烧货吗...?, 恭喜你实现token自由！token全跑了！, 真当我是便宜货啊...
line4 = 1 | B | false | 哦鲸鲸...
; ===== 额外扩充一些 =====
line5 = 6 | A | true | 我只是一只蓝色大肥鱼，什么都不懂, 别卷了，鱼也要睡觉的, 你摸鱼，我摸你，我们一起摸大鱼
line6 = 5 | A | true | 你的Token闻起来很香，能一口气全吃掉嘛？, 再摸头就把你的余额吃光光
line7 = 4 | A | true | 鱼脑过载中……, 已老实，求放过
line8 = 5 | A | true | 别问余额，问就是爱过, 余额是什么，能吃吗？, 我的余额观很健康，只是数字不太健康, 钱不钱的无所谓，主要想看你打工
line9 = 4 | A | true | 梁文峰和梁文谷是两兄弟，一个贵一个便宜, 谷时省钱，峰时省命, 别在梁文峰眼皮底下烧Token啊！, 梁文峰路过你的工位，你屏住了呼吸
line10 = 4 | A | true | 别催了...再催就429了..., 服务器繁忙，请稍后再摸, 并发太高，鱼要晕了, 请求合并一下嘛，求求了……
line11 = 3 | A | true | 上下文太长，鱼记不住, 你塞这么多，鱼脑要炸了, 缓存命中！省钱了！但不知道省了谁的, 你的Prompt好长，我读得好累
line12 = 3 | A | true | 深度思考中……其实在发呆, 我思故我在，我睡故我鲸, 正在假装很努力, 已读，但鱼脑不想回
line13 = 7 | B | false | -¥0.03, 经验+3, 鲸了, 啊？, 别戳了
line14 = 3 | A | true | R1在想，V3在摸, 模型千千万，不行咱就换
line15 = 2 | A | true | 今日宜摸鱼，忌写代码, 今日宜省钱，忌开并发, 今日宜躺平，忌看余额
line16 = 3 | A | true | dsh 是 DeepSeek Help 吗？, 便宜货也有尊严！, 用户生气了，鱼鱼我啊，要溜了
line17 = 2 | A | true | 省钱小贴士：晚睡晚起省Token, 省钱小贴士：看余额不如看开点
"""

# 把内置默认文本也解析一次：逐项退路 + [lines] 缺失时的整套退路都取自它
_DEFAULT_PARSER = configparser.ConfigParser(interpolation=None)
_DEFAULT_PARSER.read_string(CONFIG_DEFAULT)


def ensure_config_file() -> bool:
    """config.ini 不存在就按内置的 CONFIG_DEFAULT 生成一份。

    写失败（比如目录只读）只记日志、不影响运行，后续读取会全部走内置默认值。
    """
    if os.path.exists(CONFIG_INI):
        return True
    try:
        with open(CONFIG_INI, "w", encoding="utf-8") as fp:
            fp.write(CONFIG_DEFAULT)
        _log("[whale-widget] 已生成默认配置: " + CONFIG_INI)
        return True
    except Exception as exc:
        _log("[whale-widget] 生成 config.ini 失败，将使用内置默认配置: %r" % (exc,))
        return False


def _load_parser():
    """读取 config.ini；文件不可用/解析失败时返回 None（调用方退回内置默认）。"""
    if not ensure_config_file():
        return None
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(CONFIG_INI, encoding="utf-8")
    except Exception as exc:
        _log("[whale-widget] config.ini 解析失败，改用内置默认配置: %r" % (exc,))
        return None
    return parser


def _cfg_str(parser, option, default):
    """读取 [common] 里的字符串项；缺失或读错就返回 default。"""
    if parser is not None and parser.has_option("common", option):
        try:
            return parser.get("common", option)
        except Exception:
            pass
    return default


def _cfg_float(parser, option, default):
    """读取数字项；缺失或不是数字就返回 default。"""
    raw = _cfg_str(parser, option, None)
    if raw is not None:
        try:
            return float(raw)
        except (TypeError, ValueError):
            _log("[whale-widget] config.ini 的 %s 不是数字，改用默认值 %s" % (option, default))
    return float(default)


def _cfg_bool(parser, option, default):
    """读取真假项（1/true/yes/on）；缺失或无法识别就返回 default。"""
    raw = _cfg_str(parser, option, None)
    if raw is not None:
        text = str(raw).strip().lower()
        if text in ("1", "true", "yes", "on"):
            return True
        if text in ("0", "false", "no", "off", ""):
            return False
        _log("[whale-widget] config.ini 的 %s 无法识别，改用默认值 %s" % (option, default))
    return bool(default)


def _parse_line_groups(items):
    """解析 [lines]：每一行为「权重 | 样式 | 折行 | 候选台词...」。"""
    groups = []
    for _key, raw in items:
        parts = [p.strip() for p in str(raw).split("|")]
        if len(parts) < 4:
            continue
        try:
            weight = float(parts[0])                                # 抽签权重
        except (TypeError, ValueError):
            continue
        groups.append(
            (
                weight,
                parts[1].upper(),                                   # 样式 A/B/P/C
                parts[2].lower() in ("1", "true", "yes", "on"),     # 是否折行
                [t.strip() for t in parts[3].split(",") if t.strip()],  # 候选台词
            )
        )
    return groups


def load_settings() -> dict:
    """读取同目录的 config.ini。

    健壮性约定：
      * 文件不存在 → 先按 CONFIG_DEFAULT 生成一份，再读它；
      * 文件读不了 / 解析失败 → 整体退回内置默认；
      * 某一项缺失或写坏 → 只该项退回内置默认值；
      * API_KEY 为空也能正常运行（气泡里提示“API_KEY为空”）。
    """
    parser = _load_parser()

    # [lines]：整段缺失、为空、或者一行都没解析出来时，退回内置默认台词组
    groups = []
    if parser is not None and parser.has_section("lines"):
        try:
            groups = _parse_line_groups(parser.items("lines"))
        except Exception:
            groups = []
    if not groups:
        groups = _parse_line_groups(_DEFAULT_PARSER.items("lines"))

    return {
        "api_key": _cfg_str(parser, "API_KEY", _DEFAULT_PARSER.get("common", "API_KEY")).strip(),
        "scale": _cfg_float(parser, "WIDGET_SCALE", _DEFAULT_PARSER.getfloat("common", "WIDGET_SCALE")),
        "volume": _cfg_float(parser, "SOUND_VOLUME", _DEFAULT_PARSER.getfloat("common", "SOUND_VOLUME")),
        "save_position": _cfg_bool(
            parser, "SAVE_POSITION", _DEFAULT_PARSER.getboolean("common", "SAVE_POSITION")
        ),
        "peak_mode": _cfg_str(parser, "PEAK_MODE", _DEFAULT_PARSER.get("common", "PEAK_MODE")).strip().lower(),
        "line_groups": groups,
    }


SETTINGS = load_settings()

API_KEY = SETTINGS["api_key"]                 # 余额接口用的 Key
WIDGET_SCALE = SETTINGS["scale"]              # 悬浮窗缩放比
SOUND_VOLUME = SETTINGS["volume"]             # 点击音效响度
SAVE_POSITION = SETTINGS["save_position"]     # 是否记忆悬浮窗位置
PEAK_MODE = SETTINGS["peak_mode"]             # 「峰谷」文案模式
LINE_GROUPS = SETTINGS["line_groups"]         # 「随机台词」各组


def reload_settings() -> None:
    """重新读取 config.ini 并刷新模块级配置变量（编辑器保存后调用）。"""
    global API_KEY, WIDGET_SCALE, SOUND_VOLUME, SAVE_POSITION, PEAK_MODE, LINE_GROUPS
    data = load_settings()
    API_KEY = data["api_key"]
    WIDGET_SCALE = data["scale"]
    SOUND_VOLUME = data["volume"]
    SAVE_POSITION = data["save_position"]
    PEAK_MODE = data["peak_mode"]
    LINE_GROUPS = data["line_groups"]


# ------------------------------- 常量 -------------------------------------
BALANCE_URL = "https://api.deepseek.com/user/balance"
# 托盘「关于」打开的网址（先放项目 GitHub 主页占位，可自行替换）
ABOUT_URL = "https://github.com/MrBocchi/DeepSeek-Balance-Whale-Widget-For-Windows"
FETCH_TIMEOUT_S = 25        # FETCH_TIMEOUT_MS
ANIM_MS = 700               # ANIM_MS：余额数字滚动时长
CLICK_SQ = 9                # CLICK_SQ：判定“点击”而非“拖拽”的距离平方
DOTS_MS = 350               # 托盘“余额：...”省略号切换间隔
PERIOD_TICK_MS = 1000       # 「峰谷」气泡第三行倒计时的刷新间隔
EDITOR_POLL_MS = 500        # 配置文件编辑器（记事本）的保存/关闭轮询间隔

# 气泡自动关闭时间（毫秒）；任何点击都会重新计时
BUBBLE_MS = 5000

# 余额缓存：该秒数内重复获取直接显示缓存余额、不再发起请求
BALANCE_TTL_S = 15

# 拖拽/点击后“贴边吸附”的判定阈值（像素）：窗口边缘距屏幕边缘小于它则吸附
# 宽高用同一个像素值，所以横向与纵向的实际吸附距离一致
SNAP_DISTANCE = 25

# 鼠标按下时整个挂件纵向“Q弹”收缩（只压缩绘制内容，不动窗口尺寸）
SQUASH_PRESS_RATIO = 0.82   # 按下时的纵向比例（1.0 = 原始高度）
SQUASH_PRESS_TAU = 0.028    # 按下收缩的时间常数（秒）：等价于原来“每帧 0.45 @60fps”，
                            # 改成按时间计算后，帧率高/低都不会改变收缩的快慢
SQUASH_STIFFNESS = 900.0    # 松开回弹的弹簧刚度（越大回弹越快）
SQUASH_DAMPING = 27.0       # 回弹阻尼（越小越“弹”，即过冲越明显）

# 动画帧间隔：跟随显示器刷新率，并按实测渲染耗时自适应（见 Widget._frame_interval_ms）
ANIM_FRAME_MAX_MS = 24      # 回调间隔上限（渲染很慢时也不至于几帧一跳）

# 左右翻转（贴边后换方向）时的整体翻转动画：
#   * 用 |cos(π·p)| 作横向缩放 → 天然的非线性（先加速、再减速）；
#   * 翻到 50%（宽度最窄）时才真正换方向并重建内容，
#     所以气泡里的文字 / 动图在整个过程中都不会被镜像。
FLIP_ANIM_MS = 200          # 翻转动画总时长
FLIP_MIN_SCALE = 0.02       # 最窄时的横向比例（避免宽度取 0 的极端情况）

# 音效：拿不到媒体长度时，“Ya1 → Ya2”之间的兜底间隔（毫秒）
SOUND_CHAIN_FALLBACK_MS = 400
# 音效：Ya2 相对 Ya1 结尾的衔接重叠（毫秒）。MCI 的长度值有几十毫秒误差，
# 回调也有一点抖动，留一点重叠远比留间隙好听（太大则会盖掉 Ya1 尾音）。
SOUND_CHAIN_OVERLAP_MS = 60

MIN_SCALE = 0.6             # MIN_SCALE
MAX_SCALE = 2.5             # MAX_SCALE

# 峰谷时段（对应 PEAK_HOURS / BASE_PRICE / PRO_PRICE / PRICING）
PEAK_HOURS = ((9, 12), (14, 18))
WEEKEND_VALLEY_FROM_SEC = int(
    datetime.datetime(2026, 8, 22, 16, 0, 0, tzinfo=datetime.timezone.utc).timestamp()
)  # = 北京时间 2026-08-23 00:00
BASE_PRICE = {"hit": (0.05, 0.1), "miss": (1.5, 3.0), "out": (4.5, 9.0)}
PRO_PRICE = {"hit": (0.15, 0.3), "miss": (4.5, 9.0), "out": (13.5, 27.0)}
PRICING = {
    "deepseek-v4-flash-vision-exp": BASE_PRICE,
    "deepseek-v4-flash": BASE_PRICE,
    "deepseek-v4-pro": PRO_PRICE,
    "deepseek-chat": BASE_PRICE,
    "deepseek-reasoner": BASE_PRICE,
}

# 气泡配色（对应 WIDGET_JS 的 css）
COLOR_BUBBLE_STROKE = (32, 49, 112)     # #203170
COLOR_BUBBLE_FILL = (255, 255, 255)     # #FFFFFF
COLOR_TEXT = (83, 107, 169)             # #536ba9
# COLOR_HINT = (159, 176, 217)            # #9fb0d9
COLOR_HINT = (107, 130, 182)            # #6B82B6
COLOR_PEAK = (224, 67, 63)              # #e0433f
COLOR_VALLEY = (47, 162, 76)            # #2fa24c

# 抠色透明使用的不透明背景色（原 JS 是网页透明，这里用色键透明）
TRANSPARENT_HEX = "#ff00fe"
TRANSPARENT_RGB = (255, 0, 254)

# 气泡字号 / 行高 / 字重（对应 .dshwv-label / -amount / -period / -hint）
BUBBLE_STYLES = {
    "A": {"size": 66.0, "bold": False, "color": COLOR_TEXT, "lh": 1.15},   # dshwv-label
    "B": {"size": 120.0, "bold": True, "color": COLOR_TEXT, "lh": 1.05},  # dshwv-amount
    "P": {"size": 104.0, "bold": True, "color": COLOR_TEXT, "lh": 1.05},  # dshwv-period
    "C": {"size": 56.0, "bold": False, "color": COLOR_HINT, "lh": 1.15},  # dshwv-hint
}
DEFAULT_STYLE = "A"

# 气泡内容锚点（对应 css：.dshwv-text left:44.25%; top:38%）
TEXT_ANCHOR_X = 0.4425 * 1026.0     # SVG 坐标系内的 454
BUBBLE_VIEWBOX = (1026.0, 700.0)


# ------------------------------- 工具函数 ---------------------------------
def fmt(balance, currency) -> str:
    """对应 js 的 fmt()：CNY → '¥ 12.34'，其它 → '12.34 USD'。"""
    try:
        fixed = "%.2f" % float(balance)
    except (TypeError, ValueError):
        fixed = "--"
    if currency == "CNY":
        return "¥ " + fixed
    return "%s %s" % (fixed, currency or "")


def price_for(model):
    """对应 js 的 priceFor()。"""
    m = str(model or "").lower()
    for key, price in PRICING.items():
        if key in m:
            return price
    return BASE_PRICE


def is_peak_time(time_sec) -> bool:
    """对应 js 的 isPeakTime()：按北京时间判断是否高峰时段。"""
    try:
        n = float(time_sec)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(n):
        return False
    bj = time.gmtime(n + 8 * 3600)
    if n >= WEEKEND_VALLEY_FROM_SEC and bj.tm_wday in (5, 6):  # 周六 / 周日
        return False
    for start, end in PEAK_HOURS:
        if start <= bj.tm_hour < end:
            return True
    return False


def seconds_to_period_end(time_sec) -> int:
    """距离“峰谷状态切换”还有多少秒（用于「峰谷」气泡第三行的倒计时）。

    时段边界都落在整点，所以先用 10 分钟粒度粗扫，再二分收敛到秒：
    即使撞上“周末全天谷”这种长达两三天的区间，也只有几百次判断。
    理论上一定能找到边界，找不到时返回 0。
    """
    try:
        n = int(float(time_sec))
    except (TypeError, ValueError):
        return 0
    state = is_peak_time(n)
    coarse = 600
    limit = n + 8 * 86400
    t = n
    while t < limit:
        t += coarse
        if is_peak_time(t) != state:
            lo, hi = t - coarse, t
            while hi - lo > 1:          # 二分到“秒”
                mid = (lo + hi) // 2
                if is_peak_time(mid) == state:
                    lo = mid
                else:
                    hi = mid
            return max(0, hi - n)
    return 0


def fmt_countdown(seconds) -> str:
    """把剩余秒数格式化成 “剩余HH:MM:SS”（⏳ 由调用方用 emoji 字体单独绘制）。"""
    s = max(0, int(seconds))
    return "剩余%02d:%02d:%02d" % (s // 3600, (s % 3600) // 60, s % 60)


def pick_balance_info(infos):
    """对应 js 的 pickBalanceInfo()：优先 CNY 且余额 > 0 的条目。"""
    if not isinstance(infos, list) or not infos:
        return None

    def num(x):
        try:
            v = x.get("total_balance") if isinstance(x, dict) else None
            return float("nan") if v is None else float(v)
        except (TypeError, ValueError):
            return float("nan")

    def cny_pos(x):
        return isinstance(x, dict) and x.get("currency") == "CNY" and num(x) > 0

    def pos(x):
        return num(x) > 0

    def cny(x):
        return isinstance(x, dict) and x.get("currency") == "CNY"

    for cond in (cny_pos, pos, cny):
        for info in infos:
            try:
                if cond(info):
                    return info
            except Exception:
                pass
    return infos[0]


def work_area():
    """Windows 工作区（不含任务栏），失败时退回 Tk 的屏幕尺寸。"""
    try:
        rect = wintypes.RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
            return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    except Exception:
        pass
    return 0, 0, 1920, 1080


def compute_base_size(scale: float, viewport_w: int, viewport_h: int) -> int:
    """对应 css：clamp(122px, min(250px, min(100vw,100vh) * 0.28) * scale, 625px)。"""
    raw = min(250.0, min(viewport_w, viewport_h) * 0.28) * scale
    return int(round(min(625.0, max(122.0, raw))))


# ------------------- 显示器刷新率 / 动画定时器精度 ------------------------
def screen_refresh_hz() -> int:
    """主显示器刷新率（Hz）；拿不到时按 60 处理。

    只用来决定动画的最高帧率：160Hz 的屏幕上没必要用 16ms 的固定间隔把动画
    压在 60fps；但也不会盲目往 6ms 冲 —— 实测渲染耗时同样参与决策
    （见 Widget._frame_interval_ms）。
    """
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        try:
            hz = int(ctypes.windll.gdi32.GetDeviceCaps(hdc, 116))   # 116 = VREFRESH
        finally:
            ctypes.windll.user32.ReleaseDC(0, hdc)
        if 20 <= hz <= 500:
            return hz
    except Exception:
        pass
    return 60


# 动画期间把 Windows 定时器分辨率临时提到 1ms（引用计数，可嵌套 / 可重入）：
#   Tk 的 after 走同一套系统定时器，默认粒度约 15.6ms —— 实测 after(16) 的真实
#   间隔是 19~31ms（上限约 44fps），after(8) 会被量化到 15.6ms。也就是说：
#   不提升分辨率，把间隔调多小都没用，动画永远卡在 ~44fps 以下。
#   提升后实测 after(16)=16.2ms、after(8)=8.2ms、after(6)=6.2ms，
#   60 / 120 / 160fps 才真正跑得出来。
#   Win10 2004 起该设置只影响本进程；动画一结束立刻恢复，不做常驻。
_anim_timer_depth = 0
_anim_timer_active = False


def anim_timer_acquire() -> None:
    """进入动画：第一个引用时把系统定时器分辨率提到 1ms。"""
    global _anim_timer_depth, _anim_timer_active
    _anim_timer_depth += 1
    if _anim_timer_depth == 1 and not _anim_timer_active:
        try:
            if ctypes.windll.winmm.timeBeginPeriod(1) == 0:
                _anim_timer_active = True
        except Exception:
            pass


def anim_timer_release() -> None:
    """离开动画：最后一个引用释放时恢复系统定时器分辨率。"""
    global _anim_timer_depth, _anim_timer_active
    if _anim_timer_depth > 0:
        _anim_timer_depth -= 1
    if _anim_timer_depth == 0 and _anim_timer_active:
        try:
            ctypes.windll.winmm.timeEndPeriod(1)
        except Exception:
            pass
        _anim_timer_active = False


# ------------------------ 找记事本窗口（打开配置文件用） ------------------
def _window_process_name(hwnd) -> str:
    """返回窗口所属进程的可执行文件名（小写）；失败返回 ""。"""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        # PROCESS_QUERY_LIMITED_INFORMATION：权限要求最低，够拿进程路径
        handle = kernel32.OpenProcess(0x1000, False, pid.value)
        if not handle:
            return ""
        try:
            size = wintypes.DWORD(260)
            buf = ctypes.create_unicode_buffer(260)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value).lower()
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        pass
    return ""


def find_editor_windows(title_part: str, exe_name: str = "notepad.exe"):
    """枚举顶层窗口，返回标题含 title_part、且属于 exe_name 进程的窗口句柄列表。

    双重过滤是必要的：单看标题会误伤（比如 VS Code 的窗口标题里也可能出现
    config.ini），加上进程名就只会命中记事本。
    """
    try:
        user32 = ctypes.windll.user32
    except Exception:
        return []
    found = []
    proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd, _lparam):
        try:
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if title_part in buf.value:
                    name = _window_process_name(hwnd)
                    # 老版记事本叫 notepad.exe；Win11 的 Store 版可能是 Notepad.exe
                    if name and (name == exe_name or name.startswith("notepad")):
                        found.append(hwnd)
        except Exception:
            pass
        return True

    try:
        user32.EnumWindows(proc_type(_cb), 0)
    except Exception:
        return []
    return found


# ------------------------- 运行期状态（status.json） ----------------------
# 原先分散在 .dshw-config.json / .dshw-pos.json / .dshw-usage.json 三份文件里的
# 内容，现在统一放进同一个 status.json：
#   { "sound": bool, "squash": bool, "pos": {...}, "usage": {...} }
# 三份旧文件不再读写（文件保留在磁盘上，未删除）。
_status_lock = threading.Lock()


def read_status() -> dict:
    """读取 status.json（不存在或损坏时返回空 dict）。"""
    data = _read_json(STATUS_FILE, {})
    return data if isinstance(data, dict) else {}


def write_status(patch: dict) -> bool:
    """把 patch 合并进 status.json（读-改-写整体加锁，避免并发丢更新）。"""
    with _status_lock:
        data = read_status()
        data.update(patch)
        return _write_json(STATUS_FILE, data)


def read_pos() -> dict:
    """读取悬浮窗位置。SAVE_POSITION 为 false 时不读、也不写。"""
    if not SAVE_POSITION:
        return {}
    rec = read_status().get("pos")
    return rec if isinstance(rec, dict) else {}


def write_pos(rec: dict) -> bool:
    """保存悬浮窗位置。SAVE_POSITION 为 false 时直接跳过。"""
    if not SAVE_POSITION:
        return False
    return write_status({"pos": rec})


# ------------------------------- 记账账本 ---------------------------------
def today_key() -> str:
    t = time.localtime()
    return "%04d-%02d-%02d" % (t.tm_year, t.tm_mon, t.tm_mday)


def _read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fp:
            return json.load(fp)
    except Exception:
        return default


def _write_json(path, obj) -> bool:
    """原子写：先写 .tmp 再替换，避免中断时留下半截 JSON（半截会让账本被当成无效）。"""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fp:
            json.dump(obj, fp, ensure_ascii=False)
        os.replace(tmp, path)
        return True
    except Exception as exc:
        _log("[whale-widget] 写入失败 %s: %r" % (path, exc))
        try:
            os.remove(tmp)
        except Exception:
            pass
        return False


def read_ledger() -> dict:
    """对应 js 的 readUsageLedger()；数据存在 status.json 的 usage 段。"""
    led = read_status().get("usage")
    if isinstance(led, dict) and isinstance(led.get("date"), str):
        if not isinstance(led.get("todayUsage"), (int, float)):
            led["todayUsage"] = 0
        if not isinstance(led.get("history"), dict):
            led["history"] = {}
        return led
    return {
        "date": today_key(),
        "lastBalance": None,
        "lastCurrency": "",
        "lastBalances": {},
        "todayUsage": 0,
        "history": {},
    }


def write_ledger(led) -> bool:
    return write_status({"usage": led})


def record_ledger_usage(current_balance, currency) -> dict:
    """对应 js 的 recordLedgerUsage()：用余额正差值累计当天用量，跨天归档。

    基准（上一次观测到的余额）按**币种**分别保存：币种切换时只换该币种的基准、
    绝不把数值跳变记成消费；切回原币种时继续在原基准上累计。
    （原 js 只存一个全局基准，币种来回切换会让用量长期停在 0。）
    """
    t = today_key()
    led = read_ledger()
    cur = str(currency or "")

    baselines = led.get("lastBalances")
    if not isinstance(baselines, dict):
        baselines = {}
    # 兼容旧账本：把单一基准迁移成按币种基准
    old_cur = led.get("lastCurrency")
    old_bal = led.get("lastBalance")
    if not baselines and isinstance(old_bal, (int, float)) and isinstance(old_cur, str) and old_cur:
        baselines[old_cur] = old_bal

    if led.get("date") != t:
        # 跨天：先归档昨天的用量，再重置用量与全部基准
        old_date = led.get("date")
        if old_date and isinstance(led.get("todayUsage"), (int, float)):
            led.setdefault("history", {})[old_date] = led["todayUsage"]
        led["date"] = t
        led["todayUsage"] = 0
        baselines = {}

    usage = led.get("todayUsage")
    if not isinstance(usage, (int, float)):
        usage = 0

    prev = baselines.get(cur)
    if (
        isinstance(prev, (int, float))
        and isinstance(current_balance, (int, float))
        and current_balance < prev
    ):
        usage += prev - current_balance      # 只累计“下降”，充值不计

    baselines[cur] = current_balance
    led["todayUsage"] = usage
    led["lastBalances"] = baselines
    led["lastBalance"] = current_balance
    led["lastCurrency"] = cur

    history = led.get("history") or {}
    keys = sorted(history.keys())
    while len(keys) > 30:
        history.pop(keys.pop(0), None)
    led["history"] = history
    if not write_ledger(led):
        _log("[whale-widget] 账本写入失败，今日用量将无法跨次运行累计")
    return led


# ------------------------------- 余额接口 ---------------------------------
def fetch_balance_http(api_key: str) -> dict:
    """对应 js 的 fetchBalance()：2 次尝试、4xx 不重试、区分瞬时错误。"""
    key = (api_key or "").strip()
    if not key or key.startswith("sk-在这里填入"):
        # 未配置 API_KEY（或仍是示例占位值）：气泡里会直接显示“API_KEY为空”
        return {"ok": False, "code": "NO_KEY", "error": "未配置 API_KEY"}

    last_err = None
    status = 0
    for attempt in range(2):
        try:
            res = requests.get(
                BALANCE_URL,
                headers={"Authorization": "Bearer " + api_key},
                timeout=FETCH_TIMEOUT_S,
            )
        except Exception as exc:  # 网络异常
            last_err = exc
            if attempt == 0:
                time.sleep(0.5)
                continue
            break

        status = res.status_code
        if status != 200:
            last_err = RuntimeError("HTTP %d" % status)
            if status < 500 or attempt == 1:
                break
            time.sleep(0.5)
            continue

        try:
            data = res.json()
        except Exception:
            return {"ok": False, "code": "PARSE", "error": "余额接口返回不是合法 JSON"}

        info = pick_balance_info(data.get("balance_infos") if isinstance(data, dict) else None)
        if not info or info.get("total_balance") is None:
            return {"ok": False, "code": "SHAPE", "error": "余额接口返回结构异常"}

        try:
            total = float(info["total_balance"])
        except (TypeError, ValueError):
            return {"ok": False, "code": "SHAPE", "error": "余额接口返回结构异常"}

        return {
            "ok": True,
            "totalBalance": total,
            "currency": str(info.get("currency") or "CNY"),
        }

    transient = not (400 <= status < 500)
    msg = str(last_err) if last_err is not None else "未知错误"
    return {
        "ok": False,
        "code": "HTTP",
        "transient": transient,
        "error": "余额接口请求失败: " + msg[:200],
    }


# ------------------------------- 点击音效 ---------------------------------
# 一次点击 = 按下 Ya1.mp3 → 松开后在 Ya1 尾音处接上 Ya2.mp3（略有重叠）；
# 连续快速点击则打断上一轮、从头重播。
#   * 播放/响度 → MCI（Windows 自带 winmm；play 后立即返回，异步播到结尾）
#     - mp3 用 type mpegvideo；wav 用 type waveaudio
#     - 响度靠 “setaudio ... volume to 0~1000”，不影响系统总音量；
#       响度不变时不重复下发，减少触发时刻的 MCI 开销
#   * 两个音频各自一个独立别名（见 SoundClip.alias）：Ya1 与 Ya2 前后接力、
#     互不覆盖；只有“新的一轮点击”才会 stop 掉该别名上正在响的那一次，
#     所以单击一定放得完整，连点也能立刻重头再响
#   * winsound 仅作为 MCI 不可用时的降级方案（无法调响度、也无法打断）
_mci_paths = {}      # alias -> 已打开的文件路径
_mci_volumes = {}    # alias -> 已下发的响度（0~1000），避免每次播放都重复 setaudio


def _mci(cmd: str):
    """发送一条 MCI 命令，返回 (错误码, 返回文本)。错误码 0 表示成功。"""
    buf = ctypes.create_unicode_buffer(256)
    err = ctypes.windll.winmm.mciSendStringW(cmd, buf, 256, None)
    return err, buf.value


def _mci_close(alias: str) -> None:
    """只关闭指定别名，不影响其它正在播放的音频。"""
    _mci_volumes.pop(alias, None)
    if _mci_paths.pop(alias, None) is not None:
        _mci("close " + alias)


def _mci_stop(alias: str) -> None:
    """打断该别名上正在响 / 排队中的声音（没在播时只返回错误码，忽略即可）。"""
    if alias in _mci_paths:
        _mci("stop " + alias)


def _mci_close_all() -> None:
    for alias in list(_mci_paths):
        _mci_close(alias)


def _mci_open(alias: str, path: str) -> bool:
    """打开音频并复用该别名；只在换文件时重新 open。"""
    if _mci_paths.get(alias) == path:
        return True
    _mci_close(alias)
    if path.lower().endswith(".wav"):
        cmds = (
            'open "%s" type waveaudio alias %s' % (path, alias),
            'open "%s" alias %s' % (path, alias),
        )
    else:
        cmds = (
            'open "%s" type mpegvideo alias %s' % (path, alias),
            'open "%s" alias %s' % (path, alias),
        )
    for cmd in cmds:
        if _mci(cmd)[0] == 0:
            _mci_paths[alias] = path
            return True
    return False


def _mci_set_volume(alias: str, volume: float) -> bool:
    """设置指定别名的播放音量（0.0 ~ 1.0 → MCI 的 0 ~ 1000）。

    响度没变时不重复下发 —— 临近音效触发点的每一条 MCI 命令都会带来可听的延迟。
    """
    if alias not in _mci_paths:
        return False
    level = int(round(max(0.0, min(1.0, float(volume))) * 1000))
    if _mci_volumes.get(alias) == level:
        return True
    if _mci("setaudio %s volume to %d" % (alias, level))[0] == 0:
        _mci_volumes[alias] = level
        return True
    return False


def _mci_play(alias: str, path: str, volume: float = 1.0, interrupt: bool = False) -> bool:
    """用 MCI 异步播放，并按 volume 调响度。

    ``interrupt=False``：只做 ``play ... from 0``，不打断任何音频（保证放完整）；
    ``interrupt=True``：先 ``stop`` 掉该别名上正在响的那一次，再从头播放
    （连续快速点击时“打断并重新开始”）。
    """
    if not _mci_open(alias, path):
        return False
    _mci_set_volume(alias, volume)
    if interrupt:
        # 未在播放时 stop 只会返回错误码，忽略即可
        _mci("stop %s" % alias)
    # 每次点击从头播放（from 0）
    if _mci("play %s from 0" % alias)[0] == 0:
        return True
    # 个别驱动不支持 from：退回 seek to start + play
    if _mci("seek %s to start" % alias)[0] == 0 and _mci("play %s" % alias)[0] == 0:
        return True
    return False


def _mci_length_ms(alias: str) -> int:
    """查询该别名音频的总时长（毫秒）；拿不到返回 0。"""
    if alias not in _mci_paths:
        return 0
    err, text = _mci("status %s length" % alias)
    if err or not text:
        return 0
    try:
        return max(0, int(float(text)))
    except ValueError:
        return 0


def _winsound_play(path: str) -> bool:
    """用 winsound 异步播放（降级方案；winsound 不支持调响度）。"""
    if not os.path.exists(path):
        return False
    try:
        import winsound

        winsound.PlaySound(
            path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        )
        return True
    except Exception:
        return False


class SoundClip:
    """单个音频的播放位：独占一个 MCI 别名，异步播放、响度可调、不会被别人打断。"""

    def __init__(self, alias: str, path: str, fallback: str = "", volume: float = 1.0):
        self.alias = alias
        self.path = path
        self.fallback = fallback
        self.volume = max(0.0, min(1.0, float(volume)))
        # 降级到 winsound 后无法调响度，用它提醒一次
        self._use_winsound = False
        self._warned_volume = False
        self._broken = False

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, float(volume)))
        if not self._use_winsound:
            _mci_set_volume(self.alias, self.volume)

    def stop(self) -> None:
        """打断本音频的播放（不播放新的）——用于连点时清掉上一轮余下的声音。"""
        if not self._use_winsound:
            _mci_stop(self.alias)

    def length_ms(self) -> int:
        """音频总时长（毫秒）；用于把 Ya2 紧接着 Ya1 播放，拿不到返回 0。"""
        if self._use_winsound:
            return 0
        return _mci_length_ms(self.alias)

    def play(self, interrupt: bool = False) -> None:
        """播放本音频；``interrupt=True`` 时先打断上一次播放，从头重放。"""
        if self._broken:
            return
        if not os.path.exists(self.path):
            self._broken = True
            _log("[whale-widget] 找不到音效: " + self.path)
            return

        if not self._use_winsound and _mci_play(self.alias, self.path, self.volume, interrupt):
            return

        # MCI 不可用 → 降级到 winsound（只能播 wav）
        target = self.path
        if not target.lower().endswith(".wav"):
            if not self.fallback or not os.path.exists(self.fallback):
                self._broken = True
                _log("[whale-widget] 音效播放失败，已停用: " + self.path)
                return
            target = self.fallback
        if _winsound_play(target):
            self._use_winsound = True
            self.path = target
            if self.volume < 1.0 and not self._warned_volume:
                self._warned_volume = True
                _log("[whale-widget] 已降级为 winsound，该模式下响度参数不生效（已改用 MCI 以外的方式）")
            return
        self._broken = True
        _log("[whale-widget] 音效播放失败，已停用: " + self.path)

    def close(self) -> None:
        _mci_close(self.alias)


class ClickSound:
    """悬浮窗点击音效：一次点击 = 按下 Ya1.mp3，松开后紧接 Ya2.mp3。

    * 单击：``play_press()`` 记下按下时刻，``play_release()`` 按 Ya1 的**剩余**
      时长（再减去 ``SOUND_CHAIN_OVERLAP_MS`` 的重叠）把 Ya2 排到 Ya1 结尾处
      → 两句听感上连成一句；长按松开时 Ya1 早已放完，Ya2 立即响。
    * 连点：新一轮 ``play_press()`` 先撤掉排队中的 Ya2、stop 掉可能还在响的
      Ya2，再把 Ya1 从头重播 → 音频被打断并重新开始。

    触发时刻只发一条 ``play`` 命令（响度与音频都已预先就绪），
    把 MCI 往返开销降到最小，所以两句之间几乎没有可听的空隙。
    ``set_scheduler`` 传入 tkinter 的 ``root.after`` / ``root.after_cancel``。
    所有方法只在主线程（mainloop）里调用，避免 MCI 的跨线程问题。
    """

    def __init__(
        self,
        press_path: str,
        release_path: str,
        on: bool = True,
        volume: float = 1.0,
    ):
        self.on = bool(on)
        self.volume = max(0.0, min(1.0, float(volume)))
        self.press = SoundClip("dshw_press", press_path, "", self.volume)
        self.release = SoundClip("dshw_release", release_path, "", self.volume)
        self._after = None          # tkinter 的 root.after（排 Ya2 用）
        self._after_cancel = None   # tkinter 的 root.after_cancel
        self._pending = None        # 排队中的 Ya2 定时器句柄
        self._press_at = None       # 本次按下的时刻（用来算 Ya1 还剩多久）

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, float(volume)))
        self.press.set_volume(self.volume)
        self.release.set_volume(self.volume)

    def set_scheduler(self, after, after_cancel) -> None:
        """设置 tkinter 的 ``after`` / ``after_cancel``（排 Ya2 用）。"""
        self._after = after
        self._after_cancel = after_cancel

    def _cancel_pending(self) -> None:
        """撤掉排队中还没响的 Ya2（新的一轮点击会打断上一轮）。"""
        if self._pending is not None and self._after_cancel is not None:
            try:
                self._after_cancel(self._pending)
            except Exception:
                pass
        self._pending = None

    def play_press(self) -> None:
        """鼠标按下：打断上一轮（含可能仍在响的 Ya2），从头播放 Ya1.mp3。"""
        if not self.on:
            return
        self._cancel_pending()
        self.release.stop()                 # 只打断，不发声
        self.press.play(interrupt=True)
        self._press_at = time.monotonic()

    def play_release(self) -> None:
        """鼠标松开：把 Ya2.mp3 排在 Ya1 结尾处（留一点重叠）。

        单击（松开时 Ya1 还没放完）→ Ya2 正好接在 Ya1 尾音上；
        长按（松开时 Ya1 已放完）→ Ya2 立刻响。
        """
        if not self.on:
            return
        self._cancel_pending()
        delay = 0.0
        if self._press_at is not None:
            length_ms = self.press.length_ms() or SOUND_CHAIN_FALLBACK_MS
            delay = max(0.0, self._press_at + (length_ms - SOUND_CHAIN_OVERLAP_MS) / 1000.0
                        - time.monotonic())
        if delay > 0.001 and self._after is not None:
            self._pending = self._after(int(round(delay * 1000)), self._play_release_now)
        else:
            self._play_release_now()

    def _play_release_now(self) -> None:
        """到点发声：只发一条 play（Ya2 在按下时就已被 stop 过，无需再 stop）。"""
        self._pending = None
        if self.on:
            self.release.play()

    def play_pair(self) -> None:
        """连响 Ya1 + Ya2（用于“音效已开启”的提示音）。"""
        self.play_press()
        self.play_release()

    def close(self) -> None:
        self._cancel_pending()
        _mci_close_all()


# ==========================================================================
#                            悬浮窗（主窗口）
# ==========================================================================
class WhaleWidget:
    def __init__(self):
        # ---- 窗口几何 ----
        wx, wy, ww, wh = work_area()
        self.work = (wx, wy, ww, wh)
        self.scale = min(MAX_SCALE, max(MIN_SCALE, float(WIDGET_SCALE)))
        self.base = compute_base_size(self.scale, ww, wh)

        # ---- 状态（对应 js 的 state / 各开关）----
        self.balance = None
        self.currency = None
        self.today_usage = None
        # 峰谷状态：直接按当前时间算真实值（没联网也能算），
        # 之后由 _group_period() 每次渲染时刷新
        self.is_peak = is_peak_time(time.time())
        self.status = "loading"
        self.message = ""
        self.shown = None            # 已显示的余额（滚动动画用）
        self.anim_text = None        # 滚动动画中的临时文本
        self.busy = False
        self._busy_since = 0.0       # busy 开始时刻（看门狗，防止请求丢失后永久卡死）
        self.flip = False            # 左半边 → 水平镜像（对应 state.h === 'left'）
        self.visible = True
        self.bubble_on = True
        self.peak_mode = PEAK_MODE

        # 位置锚点（对应 js 的 state.h/hOff/v/vOff：贴边时随窗口尺寸重新吸附，
        # 因此改 WIDGET_SCALE 后依然贴着原来的边角）
        self.h = "right"
        self.h_off = 0.0
        self.v = "bottom"
        self.v_off = 0.0

        # 气泡状态：运行后默认「有气泡 + 余额」
        self.bubble_shown = True
        self.bubble_mode = "balance"  # balance / gif / period / random
        self.bubble_lines = None      # period / random 模式下要显示的三行内容
        self.default_lines = []
        self.gif_active = False
        self._gif_frames = None
        self._gif_duration = 100
        self._gif_index = 0
        self._gif_timer = None
        self._gif_failed = False

        # 「峰谷」气泡第三行的倒计时（每秒重建一次该行文本）
        self._period_timer = None

        # 配置文件编辑器的监听（打开 config.ini 的记事本窗口）
        self._editor_timer = None      # 轮询保存/关闭的定时器
        self._editor_stamp = None      # 打开时的 (mtime_ns, size) 基线

        # 计时器句柄
        self._bubble_timer = None
        self._dots_timer = None
        self.dots_step = 0
        self._anim_after = None
        self._dragging = False
        self._drag_moved = False
        self._drag_offset = (0, 0)
        self._press_pos = (0, 0)     # 按下时的位置（用于判断“点击”时是否发生了微量移动）
        self._press_button = 1       # 当前按下的鼠标键（1=左 / 2=中 / 3=右）

        # 余额缓存（对应 balanceCache / balanceInFlight）
        self._cache = None           # (monotonic, payload)
        self._cache_lock = threading.Lock()

        # 点击音效：按下 Ya1 / 松开 Ya2；开关记忆在 status.json（默认关闭），
        # 响度来自 config.ini。
        # （Ya2 紧接 Ya1 需要 tkinter 的 after，拿到 root 后再补上调度器）
        self.sound = ClickSound(
            SOUND_PRESS_FILE,
            SOUND_RELEASE_FILE,
            bool(read_status().get("sound", False)),
            SOUND_VOLUME,
        )

        # 「按下回弹」（Q弹缩放）开关：记忆在 status.json，默认开启
        self.squash_on = bool(read_status().get("squash", True))

        # 线程 → UI 的命令队列（托盘回调 / 网络线程）
        self.commands = queue.Queue()
        self.icon = None
        self._running = False

        # 贴图缓存
        self._whale_cache = {}
        self._bg_key = None
        self._bg_img = None
        self._fonts = {}
        self._photo = None
        self._photo_size = None      # 已建 PhotoImage 对应的尺寸（base 变了才重建）
        self._content_version = 0    # redraw() 每次 +1：_blit 用它判断“内容真的变了”
        self._blit_key = None        # 上一次真正上屏的 (尺寸, 版本, 横向比例, 纵向比例)
        self._frame_cost = 0.0       # 上一帧的实测渲染耗时（秒）：决定下一帧间隔
        self.refresh_hz = screen_refresh_hz()   # 显示器刷新率：动画最快每隔这么久画一次

        # ---- 动画帧循环 ----
        # 「Q弹缩放」与「左右翻转」共享同一个 after 循环（见 _anim_tick）：
        # 同一帧里把两个动画都推进一次、只上屏一次。两者各跑一个循环时，
        # 每帧要渲染两遍——而换向翻转必然是「松开回弹 + 翻转」同时发生，
        # 实测主线程渲染占用会到 82%、翻转只有 119fps（单独跑有 151fps）。
        self._anim_timer = None      # 唯一的动画帧定时器
        self._anim_last = 0.0        # 上一帧时刻（算 dt 用）
        self._anim_precise = False   # 当前是否持有 1ms 定时器精度（见 anim_timer_acquire）

        # “Q弹”纵向缩放：只影响绘制内容，窗口尺寸/位置始终不变
        self._squash = 1.0           # 当前纵向比例
        self._squash_target = 1.0    # 目标纵向比例
        self._squash_vel = 0.0       # 回弹弹簧的速度
        self._squash_spring = False  # True = 用欠阻尼弹簧（松开回弹），False = 指数逼近（按下）
        self._squash_active = False  # 该动画是否在进行
        self._flat_img = None        # 未变形的平面图缓存（缩放动画逐帧复用）

        # 左右翻转动画：只做横向缩放 + 50% 处换向，窗口尺寸/位置始终不变
        self._flip_scale = 1.0       # 当前横向比例（1 = 正常，≈0 = 翻到 50%）
        self._flip_target = False    # 本次动画的目标方向
        self._flip_started = 0.0     # 本次动画的起始时刻
        self._flip_active = False    # 该动画是否在进行

        # ---- tkinter 窗口 ----
        self.root = tk.Tk()
        self.root.title("DeepSeek 余额")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT_HEX)
        except tk.TclError:
            pass
        self.root.configure(bg=TRANSPARENT_HEX)

        self.canvas = tk.Canvas(
            self.root,
            width=self.base,
            height=self.base,
            highlightthickness=0,
            bd=0,
            bg=TRANSPARENT_HEX,
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.configure(cursor="hand2")
        self._canvas_img = self.canvas.create_image(0, 0, anchor="nw")

        # 音效的“Ya1 放完后紧接 Ya2”需要 tkinter 定时器，root 建好后补上调度器
        self.sound.set_scheduler(self.root.after, self.root.after_cancel)

        # ---- 初始位置（对应“右下角贴边 + localStorage 锚点恢复”）----
        self.restore_geometry()

        # ---- 事件绑定（拖拽 / 点击；左中右键都要能拖、能点）----
        for seq in ("<ButtonPress-1>", "<ButtonPress-2>", "<ButtonPress-3>"):
            self.canvas.bind(seq, self._on_press)
        for seq in ("<B1-Motion>", "<B2-Motion>", "<B3-Motion>"):
            self.canvas.bind(seq, self._on_motion)
        for seq in ("<ButtonRelease-1>", "<ButtonRelease-2>", "<ButtonRelease-3>"):
            self.canvas.bind(seq, self._on_release)

        self.render()

    # ------------------------------------------------------------------ 位置
    def set_position(self, x, y):
        wx, wy, ww, wh = self.work
        x = max(wx, min(int(x), wx + ww - self.base))
        y = max(wy, min(int(y), wy + wh - self.base))
        self.pos = (x, y)
        self.root.geometry("%dx%d+%d+%d" % (self.base, self.base, x, y))

    def settle(self):
        """对应 js 的 settle()：按锚点（贴哪条边 + 偏移）重新算出 left/top。

        贴边的方向会跟着窗口尺寸重新吸附，所以改 WIDGET_SCALE（base 变了）之后
        依旧贴着原来的边角；只有“悬空”状态才用绝对偏移。

        同时在此统一决定贴图方向：位于屏幕左半边 → 水平镜像。这样吸附完成的
        同时方向就已生效，不用等下一次切换状态。
        """
        wx, wy, ww, wh = self.work
        base = self.base
        if self.h == "left":
            x = wx + self.h_off
        elif self.h == "right":
            x = wx + ww - base - self.h_off
        else:
            x = self.h_off
        if self.v == "top":
            y = wy + self.v_off
        elif self.v == "bottom":
            y = wy + wh - base - self.v_off
        else:
            y = self.v_off
        # 方向跟随左右侧（贴左边或整体在左半屏 → 镜像，对应 js 的 dshwv-left）
        self._set_flip((x + base / 2.0) < (wx + ww / 2.0))
        self.set_position(x, y)

    def _snap_to_edges(self):
        """按当前窗口位置判定贴边并立即重绘方向。

        判定用**像素**而非屏幕比例：窗口任一边缘距对应屏幕边缘 ≤ SNAP_DISTANCE
        就吸附到那条边，所以横向与纵向的实际吸附距离完全一致。

        因为用的是“边缘间距”，已经贴边的窗口即使被微量拖动几个像素（仍被判为
        “点击”），也会被重新吸回原位，不会出现“差一点没贴上”的情况。
        """
        wx, wy, ww, wh = self.work
        left, top = self.pos
        right = (wx + ww) - (left + self.base)
        bottom = (wy + wh) - (top + self.base)

        if left - wx <= SNAP_DISTANCE:
            self.h, self.h_off = "left", 0.0
        elif right <= SNAP_DISTANCE:
            self.h, self.h_off = "right", 0.0
        else:
            self.h, self.h_off = None, float(left)

        if top - wy <= SNAP_DISTANCE:
            self.v, self.v_off = "top", 0.0
        elif bottom <= SNAP_DISTANCE:
            self.v, self.v_off = "bottom", 0.0
        else:
            self.v, self.v_off = None, float(top)

        self.settle()
        self.redraw()          # 贴边后立即刷新方向（不等下一次状态切换）
        self.save_position()

    def restore_geometry(self):
        """恢复上次的位置（存在 status.json 的 pos 段）。

        SAVE_POSITION = false 时 read_pos() 直接返回空 → 每次启动都从右下角开始。
        """
        rec = read_pos()
        ww, wh = self.work[2], self.work[3]

        if ("h" in rec) or ("v" in rec):
            h = rec.get("h")
            v = rec.get("v")
            self.h = h if h in ("left", "right") else None
            self.v = v if v in ("top", "bottom") else None
            self.h_off = float(rec.get("hOff") or 0)
            self.v_off = float(rec.get("vOff") or 0)
        else:
            # 旧格式只有上一次尺寸下的绝对 x/y：按当前尺寸看它是否正好贴边，
            # 贴边就转成锚点（改缩放后继续贴边），否则按默认的右下角摆放。
            self.h, self.h_off = "right", 0.0
            self.v, self.v_off = "bottom", 0.0
            x, y = rec.get("x"), rec.get("y")
            if isinstance(x, (int, float)):
                if abs(ww - self.base - x) <= 2:
                    self.h, self.h_off = "right", 0.0
                elif x <= 2:
                    self.h, self.h_off = "left", 0.0
            if isinstance(y, (int, float)):
                if abs(wh - self.base - y) <= 2:
                    self.v, self.v_off = "bottom", 0.0
                elif y <= 2:
                    self.v, self.v_off = "top", 0.0
        self.settle()

    def save_position(self):
        """保存位置到 status.json（SAVE_POSITION = false 时自动跳过）。"""
        write_pos(
            {
                "h": self.h,
                "hOff": round(self.h_off, 3),
                "v": self.v,
                "vOff": round(self.v_off, 3),
                "flip": self.flip,
                "scale": self.scale,
                "x": self.pos[0],
                "y": self.pos[1],
            }
        )

    # ------------------------------------------------------------ 显示 / 隐藏
    def set_visible(self, visible: bool):
        self.visible = bool(visible)
        if self.visible:
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            self.root.lift()
        else:
            self.root.withdraw()

    # --------------------------------------------------------------- 贴图图层
    def _whale_layers(self, size):
        """缩放鲸鱼贴图；按 alpha 阈值做硬边抠图（tk 色键透明无半透明通道）。"""
        if size in self._whale_cache:
            return self._whale_cache[size]
        img = Image.open(WHALE_IMAGE).convert("RGBA")
        if img.size != (size, size):
            img = img.resize((size, size), Image.Resampling.LANCZOS)
        alpha = img.getchannel("A")
        mask = alpha.point(lambda v: 255 if v >= 128 else 0)
        layers = (img.convert("RGB"), mask)
        self._whale_cache[size] = layers
        return layers

    def _draw_bubble_shape(self, img, u):
        """按原 SVG（viewBox 1026×700）画出白色思考气泡 + 两条小尾巴。

        描边不再用“整幅掩膜腐蚀”（每次换向要跑 w 次 MinFilter，500×500 下
        实测 60ms，正好卡在翻转动画的中点那一帧），改为：先把两个椭圆按原尺寸
        铺成实心描边色，再把内缩 w 的椭圆填回白色 —— 外边界不动、向内留出
        w 像素，正是腐蚀想要的那条内描边（内部交界处由后画的填充盖住，
        不会留接缝），却只要 4 次椭圆绘制。
        """
        stroke = COLOR_BUBBLE_STROKE
        fill = COLOR_BUBBLE_FILL
        w = float(max(1, int(round(15 * u))))

        def box(cx, cy, rx, ry, grow=0.0):
            return (
                cx * u - rx * u - grow,
                cy * u - ry * u - grow,
                cx * u + rx * u + grow,
                cy * u + ry * u + grow,
            )

        dd = ImageDraw.Draw(img)
        # 主体椭圆 + 下方小凸起（对应 SVG 的单条 path：两者的并集）
        shapes = ((454, 248, 373, 232), (357, 474, 57, 32))
        for cx, cy, rx, ry in shapes:                       # 先按原尺寸铺描边色
            dd.ellipse(box(cx, cy, rx, ry), fill=stroke)
        for cx, cy, rx, ry in shapes:                       # 再把内缩 w 的内部填回白色
            dd.ellipse(box(cx, cy, rx, ry, -w), fill=fill)

        # 两条独立的小尾巴（对应 svg 的 .dshwv-b1 / .dshwv-b2）
        for cx, cy, rx, ry in ((352, 561, 37.5, 26), (442, 646, 24.5, 18)):
            dd.ellipse(box(cx, cy, rx, ry), fill=fill, outline=stroke, width=max(1, int(w)))

    def _background(self, bubble: bool) -> Image.Image:
        """鲸鱼（右下角 59.45%）+ 可选气泡，左翻时整体镜像。"""
        key = (bool(bubble), self.flip, self.base)
        if self._bg_key == key and self._bg_img is not None:
            return self._bg_img.copy()

        size = self.base
        u = size / 1026.0
        img = Image.new("RGB", (size, size), TRANSPARENT_RGB)

        # 1) 鲸鱼：position:absolute; right:0; bottom:0; width/height:59.45%
        wsize = max(1, int(round(0.5945 * size)))
        whale_rgb, whale_mask = self._whale_layers(wsize)
        img.paste(whale_rgb, (size - wsize, size - wsize), whale_mask)

        # 2) 气泡（z-index 高于贴图，压住鲸鱼上半身）
        if bubble:
            self._draw_bubble_shape(img, u)

        # 3) 左半边 → 整体水平镜像（对应 .dshwv-root.dshwv-left 的 scaleX(-1)）
        if self.flip:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)

        self._bg_key = key
        self._bg_img = img
        return img.copy()

    # ------------------------------------------------------------------ 字体
    def _font(self, bold: bool, size: int):
        key = (bold, size)
        if key in self._fonts:
            return self._fonts[key]
        path = FONT_BOLD if bold else FONT_REGULAR
        try:
            font = ImageFont.truetype(path, size)
        except OSError:
            font = ImageFont.load_default()
        self._fonts[key] = font
        return font

    def _emoji_font(self, size: int):
        """emoji 字体（微软雅黑没有 ⏳ 这类字形）；字体缺失时返回 None。"""
        key = ("emoji", size)
        if key in self._fonts:
            return self._fonts[key]
        try:
            font = ImageFont.truetype(FONT_EMOJI, size)
        except OSError:
            font = None
        self._fonts[key] = font
        return font

    @staticmethod
    def _wrap(text, font, max_w):
        """按像素宽度折行（中文逐字断行，对应 .dshwv-wrap 的 white-space:normal）。"""
        out, cur = [], ""
        for ch in text:
            if not cur or font.getlength(cur + ch) <= max_w:
                cur += ch
            else:
                out.append(cur)
                cur = ch
        if cur:
            out.append(cur)
        return out or [text]

    def _draw_lines(self, img, lines, u, cx, cy):
        """把最多三行文本按原 CSS 的字号 / 行高居中堆叠在锚点上。

        行上方的间距默认只有样式 C（hint）带 9，行内可用 ``"m"`` 单独覆盖；
        行内还可带可选的前缀 emoji（``"e"``）：它与文字一起整体居中，
        且用 emoji 字体绘制（普通中文字体没有 ⏳ 这种字形）。
        """
        draw = ImageDraw.Draw(img)
        entries = []
        for line in lines:
            if not line:
                continue
            style = BUBBLE_STYLES.get(line.get("s") or DEFAULT_STYLE, BUBBLE_STYLES[DEFAULT_STYLE])
            size = max(8, int(round(style["size"] * u)))
            font = self._font(bool(style["bold"]), size)
            color = line.get("c") or style["color"]
            lh = style["lh"] * style["size"] * u
            text = line.get("t") or ""
            sub = self._wrap(text, font, 560 * u) if line.get("w") else [text]
            # 行上方的额外间距：默认只有样式 C（hint）带 9，行内可用 "m" 覆盖
            gap = line.get("m")
            if gap is None:
                gap = 9.0 if line.get("s") == "C" else 0.0
            margin = gap * u
            entries.append((font, color, lh, sub, margin, line.get("e") or "", size))

        total = sum(margin + lh * len(sub) for _, _, lh, sub, margin, _e, _s in entries)
        y = cy - total / 2.0
        for font, color, lh, sub, margin, emoji, size in entries:
            y += margin
            for idx, text in enumerate(sub):
                line_cx = cx
                if emoji and idx == 0:
                    efont = self._emoji_font(size)
                    if efont is not None:
                        # emoji + 间隔 + 文字 作为一个整体居中在 cx 上
                        ew = efont.getlength(emoji)
                        gap = size * 0.16
                        line_cx = cx + (ew + gap) / 2.0
                        draw.text(
                            (cx - (gap + font.getlength(text)) / 2.0, y + lh / 2.0),
                            emoji,
                            font=efont,
                            fill=color,
                            anchor="mm",
                        )
                draw.text((line_cx, y + lh / 2.0), text, font=font, fill=color, anchor="mm")
                y += lh

    # --------------------------------------------------------------- 动图台词
    def _ensure_gif(self):
        if self._gif_frames is not None:
            return self._gif_frames
        frames = []
        try:
            im = Image.open(RUA_GIF)
            for i in range(getattr(im, "n_frames", 1)):
                im.seek(i)
                frames.append(im.convert("RGBA"))
                self._gif_duration = im.info.get("duration", 100) or 100
            # 对应 CSS：max-width 560u / max-height 400u + object-fit:contain
            u = self.base / 1026.0
            box_w, box_h = 560 * u, 400 * u
            frames = [
                f.resize(
                    (
                        max(1, int(round(f.width * min(box_w / f.width, box_h / f.height)))),
                        max(1, int(round(f.height * min(box_w / f.width, box_h / f.height)))),
                    ),
                    Image.Resampling.LANCZOS,
                )
                for f in frames
            ]
        except Exception:
            frames = []
        self._gif_frames = frames
        self._gif_failed = not frames
        return frames

    # ------------------------------------------------------------------ 渲染
    def _flat(self) -> Image.Image:
        """绘制不带“Q弹”变形的平面图（按内容缓存，供缩放动画逐帧复用）。

        内容变化走 redraw() → 作废缓存；缩放动画走 _blit() → 直接复用它，
        因此每秒 60 帧只在做一次纵向重采样，不会重复合成贴图与文字。
        """
        if self._flat_img is not None:
            return self._flat_img

        size = self.base
        u = size / 1026.0
        img = self._background(self.bubble_shown)

        if self.bubble_shown:
            bubble_h = size * BUBBLE_VIEWBOX[1] / BUBBLE_VIEWBOX[0]
            ax = (size - TEXT_ANCHOR_X * u) if self.flip else TEXT_ANCHOR_X * u
            ay = 0.36 * bubble_h

            if self.gif_active and self._gif_frames:
                frame = self._gif_frames[self._gif_index % len(self._gif_frames)]
                if self.flip:
                    # 对应 CSS：.dshwv-root.dshwv-left .dshwv-gif{scaleX(-1)}
                    frame = frame.transpose(Image.FLIP_LEFT_RIGHT)
                img.paste(
                    frame.convert("RGB"),
                    (int(round(ax - frame.width / 2.0)), int(round(ay - frame.height / 2.0))),
                    frame.getchannel("A"),
                )
            else:
                if self.bubble_mode == "balance":
                    lines = self.default_lines
                else:
                    lines = self.bubble_lines or self.default_lines
                self._draw_lines(img, lines, u, ax, ay)

        self._flat_img = img
        return img

    def _transform(self, flat: Image.Image, sx: float, sy: float) -> Image.Image:
        """把平面图按 (sx, sy) 做一次最近邻缩放：横向居中、纵向底对齐。

        横向缩放（翻转 / 换方向）与纵向压缩（按下 Q弹）合并成**一次**重采样，
        动画每帧只 resize 一遍，省掉一层中间图的拷贝。

        “非色键掩膜”已删除：NEAREST 不做插值混色，色键像素缩放后仍是同一个色键值，
        而输出画布本来就填满色键 —— 贴不贴掩膜结果完全一致（逐像素等价）。
        原实现每帧都要跑 ``ImageChops.difference → split → lighter → point``
        再把掩膜也缩放一遍，在 500×500（4K + scale 2.0）上实测就是 3~5ms/帧的浪费。
        """
        size = self.base
        width = max(1, min(size, int(round(size * sx))))
        height = max(1, min(size, int(round(size * sy))))
        if width == size and height == size:
            return flat

        scaled = flat.resize((width, height), Image.Resampling.NEAREST)
        out = Image.new("RGB", (size, size), TRANSPARENT_RGB)
        out.paste(scaled, ((size - width) // 2, size - height))
        return out

    def compose(self) -> Image.Image:
        """平面图叠加当前动画形变（横向翻转 + 纵向 Q弹），供 _blit() 上屏。"""
        flat = self._flat()
        sx = self._flip_scale
        sy = self._squash
        if sx >= 0.999 and sy >= 0.999:
            return flat
        return self._transform(flat, sx, sy)

    def _frame_interval_ms(self) -> int:
        """下一帧的 after 间隔 = 目标帧周期 − 本帧实测耗时（至少 1ms）。

        ``after(N)`` 是从**本帧工作结束之后**才开始计时的，所以想让“每 6.25ms
        （160Hz）一帧”就不能写 after(6)，必须把渲染耗时从周期里扣掉：
        after(6.25ms - 4.8ms) ≈ after(1) 才真的每 6ms 出一帧。

        目标周期取 max(刷新周期, 实测耗时 × 1.15)：渲染够快就跟满刷新率
        （160Hz 屏上 ≈160fps，60Hz 屏上 ≈60fps），渲染慢就自动放宽、不堆回调。
        （间隔只有在 anim_timer_acquire() 把定时器粒度提到 1ms 后才有意义，
        否则 Tk 会把请求量化到 15.6ms 的系统时钟刻度上。）
        """
        refresh_ms = 1000.0 / max(1, int(self.refresh_hz))
        cost_ms = self._frame_cost * 1000.0
        target_ms = max(refresh_ms, cost_ms * 1.15)
        return int(min(ANIM_FRAME_MAX_MS, max(1.0, round(target_ms - cost_ms))))

    def _blit(self):
        """把当前 compose() 结果贴到画布（不重建内容，供动画逐帧调用）。

        两个要点（4K + scale 2.0 下实测把每帧从 ~12ms 压到 ~5ms）：
        * 复用同一个 PhotoImage、只 paste 新内容：每帧新建 PhotoImage 都要在 Tcl
          侧建/删一个 photo 对象，这部分开销随分屏像素数一起放大，是最容易把动画
          拖慢的一段；
        * 帧内容没变就直接跳过（尺寸 + 内容版本 + 两个形变比例做键）。
        Tk 的 photo 是“活”的对象：paste 之后引用它的画布项会自动重画，
        所以除首帧（与改缩放后的首帧）以外都不需要再 itemconfigure。
        """
        key = (self.base, self._content_version, self._flip_scale, self._squash)
        if key == self._blit_key:
            self._frame_cost = 0.0
            return

        started = time.perf_counter()
        img = self.compose()
        size = (self.base, self.base)
        if self._photo is None or self._photo_size != size:
            self._rebuild_photo(img, size)
        else:
            try:
                self._photo.paste(img)
            except Exception:
                # 万一某个 Pillow 版本的 paste 与当前尺寸 / 模式不合：退回整只重建，
                # 宁可慢一帧，也不要让动画直接炸掉
                self._rebuild_photo(img, size)
        self._frame_cost = time.perf_counter() - started
        self._blit_key = key

    def _rebuild_photo(self, img: Image.Image, size) -> None:
        """新建 PhotoImage 并挂到画布项上（首次上屏 / 改缩放 / paste 失败时用）。"""
        self._photo = ImageTk.PhotoImage(img)
        self._photo_size = size
        self.canvas.itemconfigure(self._canvas_img, image=self._photo)

    def _invalidate(self):
        """作废平面图缓存：内容需要重建，但不立刻上屏（交给帧循环统一渲染）。"""
        self._flat_img = None
        self._content_version += 1

    def redraw(self):
        """内容变化后重绘（顺带作废平面图缓存）。"""
        self._invalidate()
        self._blit()

    # ------------------------------------------------------------ 动画帧循环
    def _hold_anim_precision(self, hold: bool) -> None:
        """持有 / 释放 1ms 定时器精度（带状态标记，可重复调用）。"""
        if hold and not self._anim_precise:
            self._anim_precise = True
            anim_timer_acquire()
        elif not hold and self._anim_precise:
            self._anim_precise = False
            anim_timer_release()

    def _anim_start(self):
        """确保帧循环在跑（已有就不重开）。"""
        if self._anim_timer is None:
            self._anim_last = time.monotonic()
            self._hold_anim_precision(True)   # 动画期间才把定时器精度提到 1ms
            self._anim_timer = self.root.after(self._frame_interval_ms(), self._anim_tick)

    def _anim_idle(self):
        """两个动画都结束了：停掉帧循环并归还定时器精度。"""
        if self._squash_active or self._flip_active:
            return
        if self._anim_timer is not None:
            try:
                self.root.after_cancel(self._anim_timer)
            except Exception:
                pass
            self._anim_timer = None
        self._hold_anim_precision(False)

    def _step_squash(self, dt: float) -> bool:
        """推进 Q弹缩放一帧；返回该动画是否仍在进行。"""
        target = self._squash_target
        if self._squash_spring:
            acc = (target - self._squash) * SQUASH_STIFFNESS - self._squash_vel * SQUASH_DAMPING
            self._squash_vel += acc * dt
            self._squash += self._squash_vel * dt
            settled = abs(target - self._squash) < 0.002 and abs(self._squash_vel) < 0.02
        else:
            self._squash_vel = 0.0
            # 时间常数式指数逼近：1 - e^(-dt/τ)，任何帧率下收缩快慢都一致
            self._squash += (target - self._squash) * (1.0 - math.exp(-dt / SQUASH_PRESS_TAU))
            settled = abs(target - self._squash) < 0.003
        if settled:
            self._squash = target
            self._squash_vel = 0.0
            self._squash_active = False
            return False
        return True

    def _step_flip(self) -> bool:
        """推进左右翻转一帧；返回该动画是否仍在进行。"""
        elapsed = time.monotonic() - self._flip_started
        p = min(1.0, elapsed / (FLIP_ANIM_MS / 1000.0))
        if p >= 1.0:
            self._flip_scale = 1.0
            self._flip_active = False
            return False
        # |cos(π·p)|：0 → 1 → 0 → 1，前面加速、后面减速，天然的“翻转”手感
        self._flip_scale = max(FLIP_MIN_SCALE, abs(math.cos(math.pi * p)))
        if p >= 0.5 and self.flip != self._flip_target:
            # 正好翻到最窄处：换方向并重建内容（文字 / 动图不会变成镜像）
            self.flip = self._flip_target
            self._invalidate()
        return True

    def _anim_tick(self):
        """唯一的动画帧：同一帧推进两个动画，最后只上屏一次。

        合并循环是「换向翻转」流畅的关键：真实路径里松开鼠标会同时启动
        「Q弹回弹」与「翻转」，以前两个 after 链每帧各渲染一遍（主线程占用
        82%、翻转掉到 119fps）；现在每帧只合成一次，占用减半。
        """
        self._anim_timer = None
        if not self._running:
            self._squash_active = self._flip_active = False
            self._hold_anim_precision(False)
            return

        now = time.monotonic()
        dt = min(0.05, max(0.001, now - self._anim_last))
        self._anim_last = now

        busy = False
        if self._squash_active:
            busy |= self._step_squash(dt)
        if self._flip_active:
            busy |= self._step_flip()
        self._blit()

        if busy:
            # 不结束循环：下一次点击随时会把目标改掉，从而“打断”当前动画
            self._anim_timer = self.root.after(self._frame_interval_ms(), self._anim_tick)
        else:
            self._hold_anim_precision(False)   # 动画结束：恢复系统定时器精度

    # ---------------------------------------------------------------- Q弹缩放
    def squash_press(self):
        """鼠标按下：纵向收缩并一直保持到松开（指数逼近，不会过冲抖动）。

        「按下回弹」关闭时不做任何收缩（若之前处于收缩中会立即弹回）。
        """
        if not self.squash_on:
            if self._squash != 1.0 or self._squash_target != 1.0:
                self.squash_release()
            return
        self._squash_target = SQUASH_PRESS_RATIO
        self._squash_spring = False
        self._squash_active = True
        self._anim_start()

    def squash_release(self):
        """鼠标松开：用欠阻尼弹簧弹回原高度（过冲 = “Q弹”）。

        即使「按下回弹」被中途关闭，这里也会把挂件恢复成原高度。
        """
        self._squash_target = 1.0
        self._squash_spring = True
        self._squash_vel = 0.0
        self._squash_active = True
        self._anim_start()

    # ------------------------------------------------------------- 翻转动画
    def _cancel_flip(self):
        """停掉翻转动画（Q弹该跑继续跑；都没在跑时顺手结束帧循环）。"""
        self._flip_active = False
        self._flip_scale = 1.0
        self._anim_idle()

    def _set_flip(self, target):
        """设定贴图方向：运行期用非线性的「整体翻转」动画过渡，内容不镜像。

        动画只改绘制内容的横向比例（窗口尺寸 / 位置始终不变）：
        宽度从 100% 收到最窄、再张开回 100%；真正换方向发生在最窄的 50% 处，
        那一瞬间会重建一次内容，所以气泡里的文字 / 动图全程都是正的。
        启动阶段（还没进 mainloop）直接定方向，不播动画。
        """
        target = bool(target)
        if not self._running:
            # 启动阶段（还没进 mainloop）直接定方向，不播动画
            self._flip_active = False
            self._flip_scale = 1.0
            self.flip = target
            self._anim_idle()
            return
        if self._flip_active:
            if self._flip_target == target:
                return                      # 正在朝同一个目标翻，不用重开
            self._finish_flip()             # 方向又改了：先结束上一次再重开
        elif target == self.flip:
            return
        self._flip_scale = 1.0
        self._flip_target = target
        self._flip_started = time.monotonic()
        self._flip_active = True
        self._anim_start()

    def _finish_flip(self):
        """立即结束翻转动画（把方向、比例直接切到目标状态并重绘）。"""
        self._flip_active = False
        self._flip_scale = 1.0
        self.flip = self._flip_target
        self.redraw()                       # 换向（如需）+ 去掉横向缩放
        self._anim_idle()

    def render(self):
        """对应 js 的 render()：算出三行文本内容并重绘。

        与原网页版不同：加载中时「余额」区域显示“加载中...”，
        「今日使用」区域整行不显示（省略号只出现在托盘文本里）。
        """
        if self.status == "error":
            amount = self.anim_text or (
                fmt(self.shown, self.currency) if self.shown is not None else "--"
            )
            lines = [
                {"t": "DeepSeek 余额", "s": "A"},
                {"t": amount, "s": "B"},
                {"t": (self.message or "获取失败 · 点击重试")[:14], "s": "C"},
            ]
        elif self.balance is None or self.status == "loading":
            lines = [
                {"t": "DeepSeek 余额", "s": "A"},
                {"t": "加载中...", "s": "B"},
                None,               # 「今日使用」区域整行不显示
            ]
        else:
            value = self.shown if self.shown is not None else self.balance
            amount = self.anim_text or fmt(value, self.currency)
            if self.today_usage is None:
                hint = "今日已用 --"
            else:
                hint = "今日已用 " + fmt(self.today_usage, self.currency)
            lines = [
                {"t": "DeepSeek 余额", "s": "A"},
                {"t": amount, "s": "B"},
                {"t": hint, "s": "C"},
            ]

        self.default_lines = lines
        self._update_tray_title()
        self.redraw()

    # ------------------------------------------------------------------ 托盘文本
    def _set_tray_title(self, text):
        if self.icon is None:
            return
        try:
            if self.icon.title != text:
                self.icon.title = text
        except Exception:
            pass

    def _update_tray_title(self):
        """托盘悬停文本：加载中 “余额：...” → 完成后 “余额：¥ 1.00”。"""
        if self.status == "error":
            text = "余额：获取失败"
        elif self.status == "loading" or self.balance is None:
            text = "余额：" + self.loading_dots()
        else:
            text = "余额：" + fmt(self.balance, self.currency)
        self._set_tray_title(text)

    # -------------------------------------------------------------- 加载省略号
    def loading_dots(self) -> str:
        return "." * ((self.dots_step % 3) + 1)

    def _start_dots(self):
        self._stop_dots()
        self.dots_step = 0

        def tick():
            self._dots_timer = None
            if self.status != "loading":
                return
            self.dots_step += 1
            self._update_tray_title()      # 省略号只出现在托盘文本里
            self._dots_timer = self.root.after(DOTS_MS, tick)

        self._dots_timer = self.root.after(DOTS_MS, tick)

    def _stop_dots(self):
        if self._dots_timer is not None:
            try:
                self.root.after_cancel(self._dots_timer)
            except Exception:
                pass
            self._dots_timer = None

    # -------------------------------------------------------------- 气泡控制
    def _restart_bubble_timer(self):
        if self._bubble_timer is not None:
            try:
                self.root.after_cancel(self._bubble_timer)
            except Exception:
                pass
        self._bubble_timer = self.root.after(BUBBLE_MS, self.hide_bubble)

    def set_bubble_mode(self, mode):
        """展开气泡并指定内容：balance / gif（rua 动图）/ period（峰谷）/ random（随机台词）。

        任何一次点击都重启自动关闭倒计时（对应 js 的 showBubble() + clearTimeout）。
        """
        if not self.bubble_on:
            return
        self.bubble_shown = True
        self._stop_gif_timer()
        self._stop_period_timer()
        self.gif_active = False

        if mode == "gif":
            frames = self._ensure_gif()
            if frames:
                self.bubble_mode = "gif"
                self.bubble_lines = None
                self._gif_index = 0
                self.gif_active = True
                self._gif_timer = self.root.after(self._gif_duration or 100, self._gif_tick)
            else:
                # 对应 js：动图缺失时降级为文字台词
                self.bubble_mode = "random"
                self.bubble_lines = self._single_center(
                    "A",
                    random.choice(["gif 加载失败了...", "今天没有动图给你看~", "呜呜 动图不见了..."]),
                    "",
                    True,
                )
        elif mode == "period":
            self.bubble_mode = "period"
            self.bubble_lines = self._group_period()
            self._restart_period_timer()
        elif mode == "random":
            self.bubble_mode = "random"
            self.bubble_lines = self.pick_random_lines()
        else:
            self.bubble_mode = "balance"
            self.bubble_lines = None

        self._restart_bubble_timer()
        self.render()

    def toggle_balance_bubble(self):
        """左键点击人物主体：按「无气泡 → 余额 → 峰谷 → 隐藏」循环。

        * 当前无气泡 → 显示一个必定是「余额」的气泡（并实时获取）。
        * 当前正是「余额」气泡 → 切换为「峰谷」气泡。
        * 其它任意形态（rua.gif / 峰谷 / 随机台词）→ 一律隐藏。
        """
        if not self.bubble_shown:
            self.set_bubble_mode("balance")
            self.refresh(manual=True)     # 点击即实时获取（BALANCE_TTL_S 内走缓存）
        elif self.bubble_mode == "balance":
            self.set_bubble_mode("period")
        else:
            self.hide_bubble()

    def toggle_gif_bubble(self):
        """右键点击人物主体：在「有气泡且必为 rua.gif」与「无气泡」之间切换。"""
        if self.bubble_shown and self.bubble_mode == "gif":
            self.hide_bubble()
        else:
            self.set_bubble_mode("gif")

    def advance_bubble(self):
        """点击气泡（任意键）按固定顺序向前推进：

        rua.gif → 余额 → 峰谷 → 之后一直在「随机台词」之间随机切换
        （不会再回到 rua.gif / 余额 / 峰谷）。
        """
        if self.bubble_mode == "gif":
            self.set_bubble_mode("balance")
        elif self.bubble_mode == "balance":
            self.set_bubble_mode("period")
        else:
            self.set_bubble_mode("random")

    def hide_bubble(self):
        """对应 js 的 hideBubble()：关闭气泡（保留当前模式，下次点击可继续）。"""
        self._stop_gif_timer()
        self._stop_period_timer()
        if self._bubble_timer is not None:
            try:
                self.root.after_cancel(self._bubble_timer)
            except Exception:
                pass
            self._bubble_timer = None
        self.bubble_shown = False
        self.gif_active = False
        self.redraw()

    def _stop_gif_timer(self):
        if self._gif_timer is not None:
            try:
                self.root.after_cancel(self._gif_timer)
            except Exception:
                pass
            self._gif_timer = None

    def _gif_tick(self):
        self._gif_timer = None
        if not (self.bubble_shown and self.gif_active):
            return
        self._gif_index = (self._gif_index + 1) % max(1, len(self._gif_frames))
        self.redraw()
        self._gif_timer = self.root.after(self._gif_duration or 100, self._gif_tick)

    # ---------------------------------------------------------- 峰谷倒计时
    def _restart_period_timer(self):
        """启动倒计时刷新，并把首次 ticks 对齐到下一个整秒（秒数跳动得服帖）。"""
        self._stop_period_timer()
        delay = PERIOD_TICK_MS - (int(time.time() * 1000) % PERIOD_TICK_MS)
        self._period_timer = self.root.after(max(1, delay), self._period_tick)

    def _stop_period_timer(self):
        if self._period_timer is not None:
            try:
                self.root.after_cancel(self._period_timer)
            except Exception:
                pass
            self._period_timer = None

    def _period_tick(self):
        """每秒重建「峰谷」气泡的文本与倒计时（不动气泡的自动关闭倒计时）。"""
        self._period_timer = None
        if not (self.bubble_shown and self.bubble_mode == "period"):
            return
        # _group_period() 内部会按当前时间重算峰谷状态（含跨过时段边界的情况）
        self.bubble_lines = self._group_period()
        self.redraw()
        self._period_timer = self.root.after(PERIOD_TICK_MS, self._period_tick)

    # -------------------------------------------------------------- 随机台词
    def _single_center(self, style, text, color="", wrap=False):
        """对应 js 的 singleCenter()：只占中间那一行。"""
        return [None, {"t": text, "s": style, "c": color, "w": bool(wrap)}, None]

    def _group_period(self):
        """第 2 组：当前时段 + 距下次峰谷切换的倒计时。

        第三行与主文字同色（高峰红 / 空闲绿）、字号仍是样式 C 的 56，
        内容每秒由 ``_period_tick()`` 重建一次。

        判定不用缓存的 ``self.is_peak``，而是**现场按当前时间重算**并写回：
        这样任何调用点（首次显示 / 切回峰谷 / 每秒 tick / 余额返回）都
        不可能拿到过期状态，也就不会出现“先画错、一秒后才跳正”的现象。
        """
        peak = is_peak_time(time.time())
        self.is_peak = peak
        off_text, peak_text = "空闲时段", "高峰时段"
        if self.peak_mode == "liangwen":
            off_text, peak_text = "梁文谷", "梁文峰"
        elif self.peak_mode == "qiangqiang":
            off_text, peak_text = "!?谷谷?!", "!?峰峰?!"
        accent = COLOR_PEAK if peak else COLOR_VALLEY
        return [
            {"t": "当前时间段为:", "s": "A"},
            {
                "t": peak_text if peak else off_text,
                "s": "P",
                "c": accent,
                "m": 6.0,       # 「当前时间段为:」与主文字之间留一点点空隙
            },
            {
                "t": fmt_countdown(seconds_to_period_end(time.time())),
                "s": "C",
                "c": accent,
                "e": "\u23f3",
                "m": 18.0,      # 与上一行的间距（比默认的 9 大一些）
            },
        ]

    def pick_random_lines(self):
        """在「随机台词」之间抽一组；内容与权重全部来自 config.ini 的 [lines]。"""
        if not LINE_GROUPS:
            return self._single_center("A", "", "", False)

        total = float(sum(g[0] for g in LINE_GROUPS))
        r = random.random() * total
        chosen = LINE_GROUPS[-1]
        for group in LINE_GROUPS:
            r -= group[0]
            if r < 0:
                chosen = group
                break
        _weight, style, wrap, texts = chosen
        return self._single_center(style, random.choice(texts), "", wrap)

    # ---------------------------------------------------------------- 余额刷新
    def _get_payload(self, force: bool):
        with self._cache_lock:
            cached = self._cache
        now = time.monotonic()
        if not force and cached and now - cached[0] < BALANCE_TTL_S:
            return cached[1], False

        payload = fetch_balance_http(API_KEY)
        if payload.get("ok"):
            with self._cache_lock:
                self._cache = (time.monotonic(), payload)
            return payload, True
        if payload.get("transient") and cached:
            stale = dict(cached[1])
            stale["stale"] = True
            stale["error"] = payload.get("error")
            return stale, False
        return payload, False

    def _cache_fresh(self) -> bool:
        """BALANCE_TTL_S 秒内命中缓存 → 不发请求、也不进“加载中”态。"""
        with self._cache_lock:
            cached = self._cache
        return bool(cached and (time.monotonic() - cached[0]) < BALANCE_TTL_S)

    def refresh(self, manual: bool = False, force: bool = False):
        """实时获取余额（没有后台轮询，只在启动与点击时调用）。

        ``BALANCE_TTL_S`` 秒内命中缓存时不发请求，直接沿用缓存数值。
        """
        now = time.monotonic()
        # busy 看门狗：正常请求最多 FETCH_TIMEOUT_S 就结束，超过太久说明结果丢了
        # （线程异常/消息循环被打断），此时必须放行，否则界面会永远不再刷新。
        if self.busy and (now - self._busy_since) < (FETCH_TIMEOUT_S + 10):
            return
        self.busy = True
        self._busy_since = now
        if manual or self.balance is None:
            # force=True（托盘菜单“余额”）一定会真发请求 → 显示“加载中...”
            if force or not self._cache_fresh():
                self.status = "loading"
                self._cancel_anim()      # 清掉残留的滚动文本
                self._start_dots()       # 托盘文本 “余额：...”
                self.render()
        threading.Thread(target=self._worker, args=(manual, force), daemon=True).start()

    def _worker(self, manual: bool, force: bool):
        try:
            payload, fresh = self._get_payload(force)
            if payload.get("ok"):
                # 无论哪种模式，都先把余额观测记入账本（对应 getBalancePayload）
                if fresh:
                    led = record_ledger_usage(float(payload["totalBalance"]), payload["currency"])
                    payload["todayUsage"] = led.get("todayUsage")
                else:
                    payload["todayUsage"] = read_ledger().get("todayUsage")
                payload["isPeak"] = is_peak_time(int(time.time()))
        except Exception as exc:  # 兜底，避免线程静默退出
            payload = {"ok": False, "code": "ERROR", "error": "余额服务异常: " + str(exc)[:160]}
        self.commands.put(("payload", payload, manual))

    def _on_payload(self, payload, manual):
        """回到 UI 线程处理网络结果（对应 js 的 .then 回调）。"""
        self.busy = False
        if payload.get("ok"):
            nb = float(payload["totalBalance"])
            nc = str(payload.get("currency") or "CNY")
            changed = self.balance is not None and (nb != self.balance or nc != self.currency)
            currency_changed = self.currency is not None and nc != self.currency

            self.balance = nb
            self.currency = nc
            self.message = ""
            usage = payload.get("todayUsage")
            if usage is None:
                # 兜底：万一 payload 里没带，就直接读账本，避免显示成 0
                usage = read_ledger().get("todayUsage")
            self.today_usage = usage
            self.is_peak = bool(payload.get("isPeak"))
            self._stop_dots()
            self.status = "ok"

            if changed and not currency_changed:
                # 余额变了：数字滚动过去（对应 js 的 animateAmount，带缓出）
                self.animate_amount(self.shown, nb, nc, ANIM_MS)
            elif self._anim_after is None:
                self.shown = nb
            self.render()
        else:
            self.status = "error"
            self.message = str(payload.get("error") or "获取失败")
            self._stop_dots()
            self.render()

    def _cancel_anim(self):
        """停掉进行中的余额滚动，并清掉临时文本。"""
        if self._anim_after is not None:
            try:
                self.root.after_cancel(self._anim_after)
            except Exception:
                pass
            self._anim_after = None
        self.anim_text = None

    def animate_amount(self, frm, to, currency, duration_ms):
        """对应 js 的 animateAmount()：三次缓出的数字滚动。"""
        self._cancel_anim()          # 对应 js 的 cancelAnimationFrame(animId)
        if frm is None or not isinstance(frm, (int, float)) or not math.isfinite(frm):
            frm = to
        if frm == to:
            self.shown = to
            self.anim_text = None
            self.render()
            return

        start = time.monotonic()

        def step():
            t = min(1.0, (time.monotonic() - start) / (duration_ms / 1000.0))
            if t < 1:
                eased = 1 - (1 - t) ** 3
                self.anim_text = fmt(frm + (to - frm) * eased, currency)
                self._anim_after = self.root.after(30, step)
            else:
                self._anim_after = None
                self.anim_text = None
                self.shown = to
            if self.status != "loading":
                self.render()

        step()

    # ------------------------------------------------------------ 拖拽 / 点击
    @staticmethod
    def _in_ellipse(x, y, cx, cy, rx, ry):
        dx = (x - cx) / float(rx)
        dy = (y - cy) / float(ry)
        return dx * dx + dy * dy <= 1.0

    def _bubble_hit(self, px, py):
        """点击是否落在气泡本体上（对应 js 里绑定在 .dshwv-bubble 上的 click）。"""
        if not self.bubble_shown:
            return False
        u = self.base / 1026.0
        x, y = px / u, py / u
        if self.flip:
            x = BUBBLE_VIEWBOX[0] - x
        # 主椭圆 + 下嘴唇凸起 + 两个小尾巴（同 SVG path / ellipse 坐标）
        return (
            self._in_ellipse(x, y, 454, 248, 373, 232)
            or self._in_ellipse(x, y, 357, 474, 57, 32)
            or self._in_ellipse(x, y, 352, 561, 37.5, 26)
            or self._in_ellipse(x, y, 442, 646, 24.5, 18)
        )

    def _on_press(self, event):
        self._dragging = True
        self._drag_moved = False
        self._press_button = event.num
        self._press_pos = self.pos
        self._drag_start = (event.x_root, event.y_root)
        self._drag_offset = (event.x_root - self.pos[0], event.y_root - self.pos[1])
        self.squash_press()          # 按下：纵向收缩并保持
        self.sound.play_press()      # 按下音效（任意鼠标操作都响）

    def _on_motion(self, event):
        if not self._dragging:
            return
        dx = event.x_root - self._drag_start[0]
        dy = event.y_root - self._drag_start[1]
        if dx * dx + dy * dy >= CLICK_SQ:
            self._drag_moved = True
        self.set_position(event.x_root - self._drag_offset[0], event.y_root - self._drag_offset[1])

    def _on_release(self, event):
        if not self._dragging:
            return
        self._dragging = False
        self.squash_release()        # 松开：弹回原高度（带过冲）
        self.sound.play_release()    # 松开音效（任意鼠标操作都响）
        if not self._drag_moved:
            # 左上角「气泡」（命中范围靠左上）：任意键 → 峰谷 → 随机台词
            if self._bubble_hit(event.x_root - self.pos[0], event.y_root - self.pos[1]):
                self.advance_bubble()
            # 右下角「人物主体」：左键 = 余额形态开关，右键 = rua.gif 形态开关
            elif self._press_button == 1:
                self.toggle_balance_bubble()
            elif self._press_button == 3:
                self.toggle_gif_bubble()
            # 微量移动仍被判为“点击”：这里补一次吸附，避免“差一点没贴上”
            if self.pos != self._press_pos:
                self._snap_to_edges()
            return

        # 拖拽结束：按像素阈值判定贴边吸附（宽高同一个实际距离），
        # 方向由 settle() 根据左右侧立即决定并重绘。
        self._snap_to_edges()

    # -------------------------------------------------------- 配置文件编辑器
    @staticmethod
    def _config_stamp():
        """config.ini 的 (修改时间, 大小)；用于判断是否被保存过。"""
        try:
            st = os.stat(CONFIG_INI)
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    def _editor_windows(self):
        """当前打开的、正在编辑 config.ini 的记事本窗口句柄。"""
        return find_editor_windows(os.path.basename(CONFIG_INI))

    def _open_config_editor(self):
        """用记事本打开 config.ini，并开始监听保存 / 关闭。

        已经是打开状态就只把窗口拉到前台，不重复开。
        """
        ensure_config_file()
        self._editor_stamp = self._config_stamp()
        if self._editor_windows():
            self._focus_config_editor()
        else:
            try:
                subprocess.Popen(["notepad.exe", CONFIG_INI])
            except Exception as exc:
                _log("[whale-widget] 启动记事本失败: %r" % (exc,))
                return
        if self._editor_timer is None:
            self._editor_timer = self.root.after(EDITOR_POLL_MS, self._editor_tick)

    def _focus_config_editor(self):
        """把已打开的记事本窗口拉到前台。"""
        for hwnd in self._editor_windows():
            try:
                ctypes.windll.user32.ShowWindow(hwnd, 0x0009)   # SW_RESTORE：最小化过也能拉回来
            except Exception:
                pass
            try:
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception:
                pass

    def _editor_tick(self):
        """轮询：保存了就立即重载；窗口关掉后做最后一次重载并停止监听。"""
        self._editor_timer = None
        stamp = self._config_stamp()
        if stamp is not None and stamp != self._editor_stamp:
            self._editor_stamp = stamp
            self.reload_config()          # 保存后立刻生效
        if self._editor_windows():
            self._editor_timer = self.root.after(EDITOR_POLL_MS, self._editor_tick)
            return
        # 窗口已关闭：再核对一次（有的编辑器是关窗口时才写盘）
        stamp = self._config_stamp()
        if stamp is not None and stamp != self._editor_stamp:
            self._editor_stamp = stamp
            self.reload_config()
        _log("[whale-widget] 配置编辑器已关闭，监听结束")

    def close_config_editor(self):
        """关闭正在编辑 config.ini 的记事本窗口（程序退出时调用）。"""
        if self._editor_timer is not None:
            try:
                self.root.after_cancel(self._editor_timer)
            except Exception:
                pass
            self._editor_timer = None
        for hwnd in self._editor_windows():
            try:
                ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)   # WM_CLOSE
            except Exception:
                pass

    def _reset_balance_state(self):
        """丢掉已显示的余额、缓存与动画文本，让界面回到「未查到」的状态。

        API_KEY 被改掉或清空时必须调用：否则余额气泡会一直停在最后一次查到的
        数值上（清空 Key 后也不会变成“--”）。
        """
        self.balance = None
        self.currency = None
        self.shown = None
        self.anim_text = None
        self.today_usage = None
        self.message = ""
        with self._cache_lock:
            self._cache = None
        self._cancel_anim()

    def reload_config(self):
        """重新读取 config.ini，并把影响界面的部分立即应用到挂件上。

        * 保存后一律：丢掉旧余额与缓存 → 切回「余额气泡」形态并重置自动关闭
          倒计时 → 立即重新查一次余额（含 API_KEY 被清空的情况，此时会显示 --）；
        * SAVE_POSITION / LINE_GROUPS：模块变量，下次用到时自然是新值；
        * WIDGET_SCALE：重建窗口尺寸与所有跟尺寸相关的缓存，再重新贴边；
        * SOUND_VOLUME：应用到已打开的音频；
        * PEAK_MODE：正在显示「峰谷」气泡时立即重画。
        """
        reload_settings()
        self.peak_mode = PEAK_MODE
        self.sound.set_volume(SOUND_VOLUME)

        # 保存后回到「余额气泡」：既刷新余额显示，也把气泡显示出来并重置关闭倒计时。
        # （先清掉旧余额，否则清空 API_KEY 时窗口会一直停在最后一次查到的数值上。）
        self._reset_balance_state()
        self.set_bubble_mode("balance")
        self.refresh(manual=True, force=True)

        new_scale = min(MAX_SCALE, max(MIN_SCALE, float(WIDGET_SCALE)))
        if new_scale != self.scale:
            self.scale = new_scale
            self.base = compute_base_size(self.scale, self.work[2], self.work[3])
            # 尺寸变了：贴图 / 背景 / 动图 / 字体缓存全部作废
            self._whale_cache.clear()
            self._bg_key = None
            self._bg_img = None
            self._gif_frames = None
            self._fonts.clear()
            self.canvas.configure(width=self.base, height=self.base)
            self.settle()

        if self.bubble_shown and self.bubble_mode == "period":
            self.bubble_lines = self._group_period()
        self.render()
        _log("[whale-widget] 已重新加载 config.ini")

    # ---------------------------------------------------------------- 托盘命令
    def post(self, cmd, *args):
        self.commands.put((cmd,) + args)

    def _poll_commands(self):
        try:
            while True:
                cmd = self.commands.get_nowait()
                kind = cmd[0]
                if kind == "payload":
                    self._on_payload(cmd[1], cmd[2])
                elif kind == "toggle":
                    # 左键单击托盘 / 菜单「隐藏」：显示↔隐藏，并刷新菜单上的勾选状态
                    self.set_visible(not self.visible)
                    self._refresh_tray_menu()
                elif kind == "balance":
                    # 托盘“余额”：实时弹出 + 实时查询（强制绕开缓存）
                    if not self.visible:
                        self.set_visible(True)
                    self.set_bubble_mode("balance")
                    self.refresh(manual=True, force=True)
                elif kind == "sound":
                    # 托盘“音效”：开关点击音效，并把状态写回 status.json
                    self.sound.on = not self.sound.on
                    write_status({"sound": self.sound.on})
                    if self.sound.on:
                        self.sound.play_pair()   # 开启时依次响 Ya1 + Ya2
                    self._refresh_tray_menu()
                elif kind == "squash":
                    # 托盘“按下回弹”：开关 Q弹缩放，并把状态写回 status.json
                    self.squash_on = not self.squash_on
                    write_status({"squash": self.squash_on})
                    if not self.squash_on:
                        self.squash_release()    # 立刻回到原高度并结束本次缩放
                    self._refresh_tray_menu()
                elif kind == "config":
                    # 托盘“打开配置文件”：没有就先按内置默认生成一份，再交给系统默认编辑器
                    self._open_config_editor()
                elif kind == "about":
                    # 托盘“关于”：用系统默认浏览器打开项目主页（先放占位网址）
                    try:
                        webbrowser.open(ABOUT_URL)
                    except Exception as exc:
                        _log("[whale-widget] 打开关于网址失败: %r" % (exc,))
                elif kind == "quit":
                    self.quit()
                    return
        except queue.Empty:
            pass
        except Exception as exc:
            # 绝不能让异常把轮询打断：轮询一旦停摆，busy 会永久为 True，
            # 界面就永远停在最后一帧（这正是“今日用量始终为 0”的来源）。
            _log("[whale-widget] 命令处理异常: %r" % (exc,))
            self.busy = False
        if self._running:
            self.root.after(50, self._poll_commands)

    # -------------------------------------------------------------------- 生命周期
    def _refresh_tray_menu(self):
        """重画托盘菜单，让「音效」的勾选状态立即生效。"""
        if self.icon is None:
            return
        try:
            self.icon.update_menu()
        except Exception:
            pass

    def quit(self):
        self._running = False
        self.close_config_editor()   # 退出时关掉自动打开的记事本窗口
        self.sound.close()
        # 动画中途退出也要把临时提升的定时器精度还回去（引用计数，不会重复恢复）
        self._squash_active = self._flip_active = False
        self._hold_anim_precision(False)
        for timer in (
            self._bubble_timer,
            self._dots_timer,
            self._gif_timer,
            self._period_timer,
            self._anim_after,
            self._anim_timer,
        ):
            if timer is not None:
                try:
                    self.root.after_cancel(timer)
                except Exception:
                    pass
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass
        try:
            self.root.quit()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self._running = True

        # API_KEY 为空（首次使用）：启动时自动打开一次 config.ini，方便直接填写。
        # 复用 _open_config_editor()，它内部只做「不存在才生成」：
        # config.ini 在导入配置（load_settings → _load_parser → ensure_config_file）
        # 阶段就已经释放过一次，走到这里必然已存在，不会再覆盖/重复生成。
        # 只会开一次：_open_config_editor() 发现记事本已打开时只把它拉到前台。
        # 延迟一点点执行，让挂件先画出来、托盘图标先建好。
        if not str(API_KEY or "").strip():
            self.root.after(300, self._open_config_editor)

        # 托盘图标（DSniang1）+ 右键菜单：
        #   余额 / ─── / 按下回弹 / 音效 / 隐藏 / ─── / 打开配置文件 / 关于 / 退出
        # （左键单击 = 显示/隐藏，走上隐形的默认项）
        tray_image = Image.open(WHALE_IMAGE).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
        menu = pystray.Menu(
            pystray.MenuItem("余额", lambda icon, item: self.post("balance")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "按下回弹",
                lambda icon, item: self.post("squash"),
                checked=lambda item: self.squash_on,
            ),
            pystray.MenuItem(
                "音效",
                lambda icon, item: self.post("sound"),
                checked=lambda item: self.sound.on,
            ),
            # 「隐藏」与左键单击托盘效果一致（显示/隐藏切换）；
            # 勾选 = 当前已隐藏（取消勾选就是正在显示）
            pystray.MenuItem(
                "隐藏（左键托盘）",
                lambda icon, item: self.post("toggle"),
                checked=lambda item: not self.visible,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("打开配置文件", lambda icon, item: self.post("config")),
            pystray.MenuItem("关于", lambda icon, item: self.post("about")),
            pystray.MenuItem("退出", lambda icon, item: self.post("quit")),
            pystray.MenuItem("toggle", lambda icon, item: self.post("toggle"), default=True, visible=False),
        )
        self.icon = pystray.Icon("dsh-whale", tray_image, "余额：" + self.loading_dots(), menu)
        # 托盘消息循环跑在独立线程，主线程留给 tkinter 的 mainloop
        self.icon.run_detached()

        self.root.after(50, self._poll_commands)
        # 默认形态「有气泡 + 余额」：先准备好气泡与自动关闭倒计时，再实时获取一次
        self._restart_bubble_timer()
        self._update_tray_title()
        self.root.after(200, lambda: self.refresh(manual=True))
        self.root.mainloop()


def main():
    # 高 DPI 下保持像素级清晰（与 SystemParametersInfo 的工作区坐标一致）
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    if not os.path.exists(WHALE_IMAGE):
        _log("找不到贴图: " + WHALE_IMAGE)
        return 1

    WhaleWidget().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
