import os
import sys
import threading
import requests
import pygame
from functools import partial
from dotenv import load_dotenv 
from openai import OpenAI
from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QMessageBox, QLabel, QScrollArea, QSizePolicy
from config import BASE_URL, API_KEY, MODEL

# 设置Qt插件路径
load_dotenv()
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = r'./.venv/Lib/site-packages/PyQt5/Qt5/plugins'

# 设置OpenAI环境变量
os.environ['OPENAI_API_BASE'] = BASE_URL
os.environ['OPENAI_API_SECRET'] = API_KEY

# 获取当前 .py 所在的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# .md 所在的目录
md_path = os.path.join(current_dir, '蜡笔小新设定.md')
# 读取 .md 文件
with open(md_path, 'r', encoding='utf-8') as f:
    md_content = f.read()

##########桌面宠物+系统托盘模块##########

class Qt_pet(QtWidgets.QWidget):
    def __init__(self):
        super(Qt_pet, self).__init__()
        self.dis_file = "img1"

        # 自动移动功能相关（必须在 icon_quit() 之前初始化，否则构建菜单会报错）
        self.dragging = False
        self.mouse_pos = QPoint()
        self.last_mouse_pos = QPoint()
        self.is_auto_move_enabled = True   # 默认开启自动走动
        self.animation_running = False     # 是否正在播放动画
        self.chat_app = None
        self._moved = False            # 左键是否移动过（区分单击/拖动）
        self.bubble = SpeechBubble()   # 余额气泡
        self._cached_balance = None    # 缓存的余额字符串（避免点击时阻塞网络查询）

        self.windowinit()
        self.icon_quit()

        self.pos_first = self.pos()
        self.timer = QTimer()
        self.timer.timeout.connect(self.img_update)
        self.timer.start(100)

        # 随机漫步定时器（每 8 秒走一次）
        self.walk_timer = QTimer()
        self.walk_timer.timeout.connect(self.random_walk)
        self.walk_timer.start(8000)

    def img_update(self):
        if self.img_num < len(self.dir2img[self.current_dir])-1:
            self.img_num += 1
        else:
            self.img_num = 0
        self.qpixmap = QtGui.QPixmap(os.path.join(self.current_dir, self.dir2img[self.current_dir][self.img_num]))
        self.lab.setMaximumSize(self.pet_width, self.pet_height)
        self.lab.setScaledContents(True)
        # 重新设置lab的大小与图片保持一致
        self.lab.setGeometry(0, 0, self.qpixmap.width(), self.qpixmap.height())
        self.lab.setPixmap(self.qpixmap)

    # 获取放图片的路径，图片文件放在同一个项目下的pet_conf文件夹中，文件夹中放具体的图片，图片的格式为N.png(比如1.png，2.png等)
    def get_conf_dir(self):
        conf_dirs = ["assets/sprites/"]
        for conf_dir in conf_dirs:
            if os.path.exists(conf_dir) and os.path.isdir(conf_dir):
                self.conf_dir = conf_dir
                for root, dirs, files in os.walk(self.conf_dir):
                    if root in conf_dirs:
                        for dir in dirs:
                            for r, _, f in os.walk(os.path.join(root, dir)):
                                if r == os.path.join(root, dir) and len(f)>0:
                                    try:
                                        f.sort(key=lambda x: int(x.split(sep='.', maxsplit=1)[0]))
                                    except ValueError:
                                        f.sort(key=lambda x: x.split(sep='.', maxsplit=1)[0])
                                    self.dir2img.update({r: f})
                        return True
        QtWidgets.QMessageBox.warning(None, "警告", "没有找到配置文件哦~", QtWidgets.QMessageBox.StandardButton.Ok)
        return False

    def windowinit(self):
        screen_rect = QApplication.desktop().availableGeometry()
        self.pet_width = 200
        self.pet_height = 200
        init_x = screen_rect.width() - self.pet_width
        init_y = screen_rect.height() - self.pet_height
        self.setGeometry(init_x, init_y, self.pet_width, self.pet_height)
        self.setWindowTitle('蜡笔小新')
        self.img_num = 0
        # 找到配置文件，失败则退出
        self.dir2img = {}
        if not self.get_conf_dir():
            self.quit()
        
        self.lab = QtWidgets.QLabel(self)
        self.current_dir = list(self.dir2img.keys())[0]
        self.qpixmap = QtGui.QPixmap(os.path.join(self.current_dir, self.dir2img[self.current_dir][self.img_num]))
        self.lab.setPixmap(self.qpixmap)
        
        # 设置窗口为 无边框 | 保持顶部显示 | 不显示任务栏图标
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint | QtCore.Qt.WindowType.Tool)
        # 设置窗口透明
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.show()

    # 音乐控制方法
    def toggle_music(self, checked):
        global music_paused
        with music_lock:
            music_paused = not checked

    def adjust_volume(self, value):
        global current_volume
        with music_lock:
            current_volume = value / 100.0

    def _style_menu(self, menu):
        """菜单圆角 + 阴影"""
        menu.setWindowFlags(menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        menu.setAttribute(Qt.WA_TranslucentBackground)
        shadow = QtWidgets.QGraphicsDropShadowEffect(menu)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QtGui.QColor(0, 0, 0, 70))
        menu.setGraphicsEffect(shadow)
        return menu

    # 构建菜单（托盘图标和宠物本体右键共用同一套）
    def build_pet_menu(self):
        menu = self._style_menu(QtWidgets.QMenu(self))

        # 切换动画
        changeSubMenu = self._style_menu(QtWidgets.QMenu("🎬 切换动画", self))
        for dir in self.dir2img.keys():
            act = QtWidgets.QAction(os.path.basename(dir), self, triggered=partial(self.changeImg, dir))
            changeSubMenu.addAction(act)
        menu.addMenu(changeSubMenu)

        # 自动走动开关
        self.enable_auto_move_action = QtWidgets.QAction("🚶 自动走动", self)
        self.enable_auto_move_action.setCheckable(True)
        self.enable_auto_move_action.setChecked(self.is_auto_move_enabled)
        self.enable_auto_move_action.triggered.connect(self.toggle_auto_move)
        menu.addAction(self.enable_auto_move_action)

        # 聊天（余额改为左键单击小新查看，天气已移除）
        menu.addAction(QtWidgets.QAction('💬 聊天', self, triggered=self.start_chat_app))

        # 音乐开关
        self.music_toggle = QtWidgets.QAction('🎵 音乐', self, checkable=True)
        self.music_toggle.setChecked(True)
        self.music_toggle.triggered.connect(self.toggle_music)
        menu.addAction(self.music_toggle)

        # 音量滑块
        volume_slider = QtWidgets.QSlider(Qt.Horizontal)
        volume_slider.setRange(0, 100)
        volume_slider.setValue(int(current_volume * 100))
        volume_slider.setFixedWidth(150)
        volume_slider.valueChanged.connect(self.adjust_volume)
        volume_action = QtWidgets.QWidgetAction(self)
        volume_action.setDefaultWidget(volume_slider)
        menu.addAction(volume_action)

        # 开机自启开关
        self.autostart_action = QtWidgets.QAction("🔌 开机自启", self)
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(self.is_autostart_enabled())
        self.autostart_action.triggered.connect(self.toggle_autostart)
        menu.addAction(self.autostart_action)

        menu.addSeparator()
        menu.addAction(QtWidgets.QAction('✖ 退出', self, triggered=self.quit))
        return menu

    # 设置系统托盘
    def icon_quit(self):
        self.mini_icon = QtWidgets.QSystemTrayIcon(self)
        self.mini_icon.setIcon(QtGui.QIcon(os.path.join(self.current_dir, self.dir2img[self.current_dir][0])))
        self.mini_icon.setToolTip("蜡笔小新")
        self.mini_icon.setContextMenu(self.build_pet_menu())
        self.mini_icon.show()

        # 定时刷新余额到托盘悬停提示（每 10 分钟一次；启动 3 秒后先查一次）
        self.balance_timer = QTimer(self)
        self.balance_timer.timeout.connect(self.update_balance_tooltip)
        self.balance_timer.start(600000)
        QTimer.singleShot(3000, self.update_balance_tooltip)

    def contextMenuEvent(self, event):
        """在宠物身上直接右键 → 弹出菜单（不用去找系统托盘）"""
        self.build_pet_menu().exec_(event.globalPos())

    def toggle_auto_move(self, checked):
        # 切换自动移动功能
        self.is_auto_move_enabled = checked

    def mousePressEvent(self, QMouseEvent):
        if QMouseEvent.button() == QtCore.Qt.MouseButton.LeftButton:
            self.dragging = True
            self._moved = False
            self.mouse_pos = QMouseEvent.globalPos()
            QMouseEvent.accept()
            self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.OpenHandCursor))

    def mouseMoveEvent(self, QMouseEvent):
        if self.dragging:
            delta = QMouseEvent.globalPos() - self.mouse_pos
            if abs(delta.x()) + abs(delta.y()) > 6:
                self._moved = True  # 移动超过阈值 → 判定为拖动而非点击
            new_pos = self.pos() + delta
            self.last_mouse_pos = self.pos()  # 记录上一次位置
            self.move(new_pos)
            self.check_edge(new_pos)  # 检测窗口是否靠近屏幕边缘
            self.mouse_pos = QMouseEvent.globalPos()

    def mouseReleaseEvent(self, QMouseEvent):
        if QMouseEvent.button() == QtCore.Qt.MouseButton.LeftButton:
            if not self._moved:
                self.show_balance_bubble()  # 没拖动 = 单击 → 弹余额气泡
            self.dragging = False
            self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.ArrowCursor))

    def check_edge(self, new_pos):
        # 检查窗口是否靠近屏幕边缘
        if self.is_auto_move_enabled and not self.animation_running:
            screen_rect = QApplication.desktop().availableGeometry(self)
            window_rect = self.geometry()

            # 获取窗口和屏幕的位置信息
            window_top = new_pos.y()
            window_bottom = new_pos.y() + window_rect.height()
            window_left = new_pos.x()
            window_right = new_pos.x() + window_rect.width()

            # 屏幕的高度和宽度
            screen_height = screen_rect.height()
            screen_width = screen_rect.width()

            # 设置边缘阈值
            edge_threshold = min(100, 0.1 * max(screen_height, screen_width))  # 边缘阈值为100像素或屏幕的10%

            # 动画速度（单位：毫秒）
            animation_speed = 10000  # 可以调整这个值来控制移动速度

            # 检查顶部
            if window_top < edge_threshold and self.last_mouse_pos.y() > edge_threshold:
                target_y = screen_height - window_rect.height() - edge_threshold
                self.start_animation(new_pos.x(), target_y, animation_speed)
            # 检查底部
            elif window_bottom > screen_height - edge_threshold and self.last_mouse_pos.y() + window_rect.height() < screen_height - edge_threshold:
                target_y = edge_threshold
                self.start_animation(new_pos.x(), target_y, animation_speed)
            # 检查左边
            elif window_left < edge_threshold and self.last_mouse_pos.x() > edge_threshold:
                target_x = screen_width - window_rect.width() - edge_threshold
                self.start_animation(target_x, new_pos.y(), animation_speed)
            # 检查右边
            elif window_right > screen_width - edge_threshold and self.last_mouse_pos.x() + window_rect.width() < screen_width - edge_threshold:
                target_x = edge_threshold
                self.start_animation(target_x, new_pos.y(), animation_speed)

    def start_animation(self, target_x, target_y, duration):
        # 启动平滑移动动画
        if self.animation_running:
            return

        self.animation = QtCore.QPropertyAnimation(self, b"pos")
        self.animation.setDuration(duration)  # 设置动画持续时间
        self.animation.setStartValue(self.pos())  # 设置动画起始位置
        self.animation.setEndValue(QtCore.QPoint(target_x, target_y))  # 设置动画目标位置
        self.animation.finished.connect(self.animation_finished)  # 动画完成后回调
        self.animation.start()
        self.animation_running = True

    def animation_finished(self):
        # 动画完成后的处理
        self.animation_running = False

    def quit(self):
        self.close()
        sys.exit()

    def changeImg(self, dir):
        self.current_dir = dir

    def start_chat_app(self):
        if not self.chat_app:
            self.chat_app = ChatApp(cost_callback=self.show_cost_bubble)
            self.chat_app.show()

    def show_balance_bubble(self):
        """左键单击小新 → 在左上角弹出肥嘟嘟左卫门气泡（优先用缓存，避免阻塞）"""
        bal = self._cached_balance or fetch_balance()
        if bal is None:
            self.bubble.show_bubble("没查到余额…", fg="#000000")
        else:
            value = _parse_balance(bal)
            if value is not None and value <= 0:
                # 余额为 0：真是伤脑筋 + 广志语音
                self.bubble.show_bubble("真是伤脑筋", fg="#E03131", duration=6000)
                self.play_hiroshi_voice()
            elif value is not None and value < LOW_BALANCE_THRESHOLD:
                # 余额告急
                self.bubble.show_bubble(f"余额告急！只剩 {bal}", fg="#E8590C", duration=6000)
            else:
                # 正常
                self.bubble.show_bubble(f"余额 {bal}", fg="#000000")
        # 定位到小新左上角
        bh = self.bubble.height()
        self.bubble.move(self.pos().x() - 10, self.pos().y() - bh - 12)

    def show_cost_bubble(self, cost):
        """聊天完成后，弹气泡显示本轮消耗（模仿 dsh 视频）"""
        self.bubble.show_bubble(f"本轮消耗 ￥{cost:.2f}", fg="#000000", duration=4000)
        bh = self.bubble.height()
        self.bubble.move(self.pos().x() - 10, self.pos().y() - bh - 12)

    def play_hiroshi_voice(self):
        """播放广志语音「真是伤脑筋」（音频需自备：assets/audio/广志真是伤脑筋.wav）"""
        path = os.path.join(current_dir, "assets", "audio", "广志真是伤脑筋.wav")
        if not os.path.exists(path):
            return
        try:
            pygame.mixer.Sound(path).play()
        except Exception:
            pass

    def update_balance_tooltip(self):
        """静默刷新托盘悬停提示为当前余额"""
        bal = fetch_balance()
        if bal:
            self._cached_balance = bal
            self.mini_icon.setToolTip(f"蜡笔小新 | 余额 {bal}")

    def random_walk(self):
        """随机漫步：每隔几秒走到屏幕上的新位置"""
        if self.dragging or self.animation_running or not self.is_auto_move_enabled:
            return
        import random
        screen = QApplication.desktop().availableGeometry()
        max_x = max(1, screen.width() - self.width())
        max_y = max(1, screen.height() - self.height())
        self.start_animation(random.randint(0, max_x), random.randint(0, max_y), 5000)

    def _startup_bat_path(self):
        appdata = os.environ.get("APPDATA", "")
        startup = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
        return os.path.join(startup, "shinchan-pet.bat")

    def is_autostart_enabled(self):
        try:
            return os.path.exists(self._startup_bat_path())
        except Exception:
            return False

    def toggle_autostart(self, checked):
        """开机自启：在 Windows 启动文件夹放一个 .bat（无需管理员权限）"""
        path = self._startup_bat_path()
        try:
            if checked:
                pyw = sys.executable.replace("python.exe", "pythonw.exe")
                if not os.path.exists(pyw):
                    pyw = sys.executable
                script = os.path.join(current_dir, "pet.py")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="gbk") as f:
                    f.write("@echo off\n")
                    f.write(f'cd /d "{current_dir}"\n')
                    f.write(f'start "" "{pyw}" "{script}"\n')
            else:
                if os.path.exists(path):
                    os.remove(path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(None, "设置失败", f"开机自启设置失败：{e}")

##########聊天模块##########

# 检查网络连接的函数
def check_internet_connection():
    try:
        # 尝试连接到深度求索（DeepSeek AI）的公共DNS服务器
        requests.get("https://www.deepseek.com", timeout=5)
        return True
    except requests.ConnectionError:
        return False

api_key = API_KEY
llm_name = MODEL
base_url = BASE_URL
client = OpenAI(api_key=api_key, base_url=base_url)

##########余额查询模块##########

def _balance_url():
    """从 BASE_URL 推导余额接口地址（DeepSeek 的余额接口在 /user/balance）"""
    base = (BASE_URL or "").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    if not base:
        base = "https://api.deepseek.com"
    return base + "/user/balance"


def fetch_balance():
    """查询账户余额，成功返回如 'CNY 6.99'，失败返回 None"""
    if not API_KEY:
        return None
    try:
        r = requests.get(
            _balance_url(),
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=10,
        )
        data = r.json()
        infos = data.get("balance_infos") or []
        if data.get("is_available") and infos:
            info = infos[0]
            return f"{info.get('currency', 'CNY')} {info.get('total_balance', '?')}"
    except Exception:
        return None
    return None


LOW_BALANCE_THRESHOLD = 5.0  # 余额低于此值视为「告急」（单位：CNY）


def _parse_balance(bal_str):
    """从 'CNY 6.50' 里提取数字 6.5"""
    if not bal_str:
        return None
    digits = ''.join(c for c in bal_str if c.isdigit() or c == '.')
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
        return None


class SpeechBubble(QtWidgets.QWidget):
    """肥嘟嘟左卫门气泡：头部图 + 余额文字在牙齿上（无图时退回纯文字标签）"""

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._head_pixmap = None

        # 头部图
        self.image_lab = QtWidgets.QLabel(self)
        self.image_lab.setAttribute(Qt.WA_TranslucentBackground)
        self.image_lab.hide()

        # 牙齿上的文字
        self.teeth_lab = QtWidgets.QLabel(self)
        self.teeth_lab.setAttribute(Qt.WA_TranslucentBackground)
        self.teeth_lab.setFont(QFont("微软雅黑", 10, QFont.Bold))
        self.teeth_lab.hide()

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

        # 预加载头部图
        head_path = os.path.join(current_dir, "assets", "zuoweimen_head.png")
        if os.path.exists(head_path):
            self._head_pixmap = QtGui.QPixmap(head_path)

    def show_bubble(self, text, fg="#3A3A3A", duration=4500):
        """显示气泡：头部图 + 文字在牙齿；图片缺失则退回纯文字标签"""
        if self._head_pixmap is not None and not self._head_pixmap.isNull():
            scaled = self._head_pixmap.scaledToWidth(280, Qt.SmoothTransformation)
            self.image_lab.setPixmap(scaled)
            self.image_lab.resize(scaled.size())
            self.image_lab.show()
            self.resize(scaled.size())
            self.teeth_lab.setText(text)
            self.teeth_lab.setStyleSheet(
                f"color: {fg}; background-color: rgba(255,255,255,215);"
                f"border-radius: 8px; padding: 3px 9px;"
            )
            self.teeth_lab.adjustSize()
            # 文字中心对准眼睛位置（额头中间）
            cx = int(scaled.width() * 0.46)
            cy = int(scaled.height() * 0.45)
            tx = max(0, cx - self.teeth_lab.width() // 2)
            ty = max(0, cy - self.teeth_lab.height() // 2)
            self.teeth_lab.move(tx, ty)
            self.teeth_lab.show()
        else:
            # 无图 fallback：纯文字圆角标签
            self.image_lab.hide()
            self.teeth_lab.setText(text)
            self.teeth_lab.setStyleSheet(
                f"color: {fg}; background-color: #FFFFFF;"
                f"border: 1px solid #EFEFEF; border-radius: 12px; padding: 8px 12px;"
            )
            self.teeth_lab.adjustSize()
            self.teeth_lab.move(0, 0)
            self.teeth_lab.show()
            self.resize(self.teeth_lab.size())
        self.show()
        self.raise_()
        self._hide_timer.start(duration)


system_prompt = '''
你是一个桌面宠物智能体，你很擅长模仿蜡笔小新(野原新之助)这个动漫角色的说话风格和用户进行交互聊天。
'''

text = md_content

def gen_prompt(context_text, user_input):
    return f"""
    根据如下《蜡笔小新》的设定和背景信息：
    {context_text}    
    请用蜡笔小新的语气和风格回答用户的这个问题
    {user_input}
    """

_last_cost = 0.0  # 最近一次对话消耗（元）


def _calc_cost(usage):
    """按 DeepSeek flash 定价计算本次消耗（元）"""
    if usage is None:
        return 0.0
    try:
        prompt_tokens = usage.prompt_tokens or 0
        completion_tokens = usage.completion_tokens or 0
    except AttributeError:
        return 0.0
    import datetime
    now = datetime.datetime.now()
    is_peak = now.weekday() < 5 and (9 <= now.hour < 12 or 14 <= now.hour < 18)
    in_price = (2.0 if is_peak else 1.0) / 1_000_000
    out_price = (8.0 if is_peak else 4.0) / 1_000_000
    return prompt_tokens * in_price + completion_tokens * out_price


def call_llm(user_input):
    global _last_cost
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": gen_prompt(text, user_input)}
    ]
    
    response = client.chat.completions.create(
        model=llm_name,
        messages=messages,
        temperature=1
    )
    _last_cost = _calc_cost(getattr(response, 'usage', None))
    return response.choices[0].message.content

# 初始化聊天历史（保持原有结构）
history = [
    {"role": "system", "content": system_prompt}
]

# 修改后的聊天函数
def chat(user_input, history):
    history.append({"role": "user", "content": user_input})
    response = call_llm(user_input)
    history.append({"role": "assistant", "content": response})
    return response

# 设置文本气泡样式
class ChatBubble(QLabel):
    def __init__(self, text, is_sender=True, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.is_sender = is_sender
        self.setWordWrap(True)
        self.setFont(QFont("微软雅黑", 10))  # 设置字体为微软雅黑，字号为10
        self.initUI()

    def initUI(self):
        # 设置气泡样式（微信式不对称圆角：贴边一侧小圆角）
        if self.is_sender:
            self.setStyleSheet("""
                QLabel {
                    background-color: #FFE082;
                    color: #3A2E1A;
                    border-radius: 12px 4px 12px 12px;
                    padding: 10px 14px;
                    margin: 4px 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                QLabel {
                    background-color: #FFFFFF;
                    color: #3A3A3A;
                    border-radius: 4px 12px 12px 12px;
                    padding: 10px 14px;
                    margin: 4px 8px;
                    border: 1px solid #EFEFEF;
                }
            """)
        # 确保高度根据内容自动调整
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(40)  # 设置最小高度，避免过小

class ChatApp(QWidget):
    def __init__(self, cost_callback=None):
        super().__init__()
        self.cost_callback = cost_callback
        self.initUI()
    
    def initUI(self):
        # 创建主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        # 设置窗口
        self.setLayout(main_layout)
        self.setWindowTitle('蜡笔小新')
        self.setGeometry(300, 300, 480, 800)
        self.setStyleSheet("background-color: #FAF7F2;")
        # 加载并设置左上角窗口图标（图标需自备，缺失时跳过）
        if os.path.exists('xiao_xin.ico'):
            icon = QIcon('xiao_xin.ico')
            self.setWindowIcon(icon)

        # 消息显示区域
        self.message_area = QWidget()
        self.message_area.setStyleSheet("background-color: #FAF7F2;")
        message_layout = QVBoxLayout(self.message_area)

        # 使用 QScrollArea 来支持消息区域的滚动
        scroll = QScrollArea()
        scroll.setWidget(self.message_area)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollBar:vertical { background: transparent; width: 6px; }
            QScrollBar::handle:vertical { background: #E0DCD3; border-radius: 3px; min-height: 30px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)
        main_layout.addWidget(scroll)

        # 创建输入框和发送按钮的布局
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(12, 10, 12, 12)
        input_layout.setSpacing(8)

        # 创建输入框
        self.input_box = QLineEdit(self)
        self.input_box.setPlaceholderText("和小新说点什么…")
        self.input_box.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #EBE6DC;
                border-radius: 20px;
                padding: 10px 16px;
                font-size: 13px;
                color: #3A3A3A;
            }
            QLineEdit:focus {
                border: 1px solid #E85A4F;
            }
        """)
        self.input_box.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_box, 1)

        # 创建发送按钮
        send_button = QPushButton('发送', self)
        send_button.clicked.connect(self.send_message)
        send_button.setCursor(Qt.PointingHandCursor)
        send_button.setStyleSheet("""
            QPushButton {
                background-color: #E85A4F;
                color: #FFFFFF;
                border: none;
                border-radius: 20px;
                padding: 10px 22px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #D94A3F;
            }
            QPushButton:pressed {
                background-color: #C93F35;
            }
        """)
        input_layout.addWidget(send_button)

        # 将输入框和发送按钮的布局添加到主布局
        main_layout.addLayout(input_layout)

        # 自动发送欢迎消息
        self.send_welcome_message()

    def send_welcome_message(self):
        # 静态欢迎语，立即显示（避免启动时调 API 导致聊天框卡顿）
        self.add_message("小新", "嗨~我是野原新之助，找我聊天吗？", is_sender=False)

    def send_message(self):
        message = self.input_box.text()
        if not message:
            return
        # 先显示用户消息
        self.add_message("你", message, is_sender=True)
        self.input_box.clear()

        # 异步调用 API，不阻塞 UI
        self._reply = [None]

        def worker():
            try:
                self._reply[0] = chat(message, history)
            except Exception as e:
                self._reply[0] = f"(小新走神了：{type(e).__name__}，稍后再试~)"

        threading.Thread(target=worker, daemon=True).start()

        # 轮询结果，返回后更新 UI
        if not hasattr(self, '_poll_timer'):
            self._poll_timer = QTimer(self)
            self._poll_timer.timeout.connect(self._poll_reply)
        self._poll_timer.start(150)

    def _poll_reply(self):
        if self._reply and self._reply[0] is not None:
            self._poll_timer.stop()
            reply = self._reply[0]
            self._reply = [None]
            self.add_message("小新", reply, is_sender=False)
            # 聊天完成后，弹气泡显示本轮消耗（模仿视频）
            if self.cost_callback and _last_cost > 0:
                self.cost_callback(_last_cost)

    def add_message(self, sender, message, is_sender):
        # 创建新的气泡并添加到消息区域
        new_message = ChatBubble(f"{sender}: {message}", is_sender=is_sender)
        self.message_area.layout().addWidget(new_message)
        # 滚动到最底部
        self.message_area.layout().update()
        scroll = self.findChild(QScrollArea)
        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())

##########音乐播放模块##########

# 在全局添加音乐控制变量
music_lock = threading.Lock()
music_paused = False
current_volume = 0.3  # 默认音量30%
playing_second = False  # 标志变量，表示是否正在播放第二首音频

def play_music():
    global music_paused, current_volume, playing_second  # 显式声明全局变量
    # 初始化pygame
    pygame.init()

    # 加载音乐文件
    music1 = './assets/audio/蜡笔小新INTRO.wav'
    music2 = './assets/audio/蜡笔小新BGM.wav'

    # 初始化当前播放的音乐索引、是否单曲循环的标志和音量
    current_track = 0

    # 加载并播放第一首音乐
    pygame.mixer.music.load(music1)
    pygame.mixer.music.play()


    # 主循环
    running = True
    while running:
        with music_lock:
            # 更新播放状态和音量
            if music_paused:
                pygame.mixer.music.pause()
            else:
                pygame.mixer.music.unpause()
            pygame.mixer.music.set_volume(current_volume)

        # 检查是否是第一次播放第一首音乐
        if not playing_second:
            if not pygame.mixer.music.get_busy():
                # 第一首音乐播放完毕，加载第二首音乐并循环播放
                pygame.mixer.music.load(music2)
                pygame.mixer.music.play(-1)  # -1 表示循环播放
                playing_second = True

        pygame.time.wait(100)

    pygame.quit()

# 在 PyQt5 的退出逻辑中，确保 pygame 停止播放
def stop_music():
    global music_paused, playing_second
    with music_lock:
        music_paused = True
        playing_second = False
        pygame.mixer.music.stop()
        pygame.quit()

##########全局样式##########

APP_QSS = """
QMenu {
    background-color: #FFFFFF;
    border: 1px solid #EFEFEF;
    border-radius: 14px;
    padding: 6px;
}
QMenu::item {
    padding: 9px 28px 9px 20px;
    margin: 2px 6px;
    border-radius: 9px;
    color: #3A3A3A;
    font-size: 13px;
}
QMenu::item:selected {
    background-color: #FFF3E0;
    color: #E85A4F;
}
QMenu::separator {
    height: 1px;
    background: #F0F0F0;
    margin: 5px 14px;
}
QMenu::indicator {
    width: 14px;
    height: 14px;
}
QMessageBox {
    background-color: #FFFFFF;
}
QMessageBox QLabel {
    color: #3A3A3A;
    font-size: 13px;
}
QMessageBox QPushButton {
    background-color: #E85A4F;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 7px 20px;
    font-size: 13px;
}
QMessageBox QPushButton:hover {
    background-color: #D94A3F;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #EFEFEF;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #E85A4F;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
"""


if __name__ == '__main__':
    # 单实例保护：绑定固定端口，绑不上说明已有实例在跑，静默退出
    import socket as _socket
    try:
        _instance_lock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        _instance_lock.bind(('127.0.0.1', 54321))
        _instance_lock.listen(1)
    except OSError:
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setStyleSheet(APP_QSS)
    app.setQuitOnLastWindowClosed(False)  # 关闭弹窗/子窗口不再导致小新退出，只靠「退出」菜单退出
    pet = Qt_pet()
    # sys.exit(app.exec_())

    # 创建并启动音乐播放线程
    music_thread = threading.Thread(target=play_music)
    music_thread.daemon = True  # 设置为守护线程，这样主线程结束时音乐播放线程也会结束
    music_thread.start()
    # 连接退出信号
    app.aboutToQuit.connect(stop_music)
    sys.exit(app.exec_())