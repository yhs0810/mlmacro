import dearpygui.dearpygui as dpg
import ctypes
import threading
import time

# 상태 변수
is_running = False

# Windows API
user32 = ctypes.windll.user32

# 가상 키 코드
VK_RIGHT = 0x27
VK_F1 = 0x70
VK_F2 = 0x71

def key_down(vk_code):
    """키 누르기 (홀드) - keybd_event 사용"""
    user32.keybd_event(vk_code, 0, 0, 0)

def key_up(vk_code):
    """키 떼기"""
    user32.keybd_event(vk_code, 0, 2, 0)  # KEYEVENTF_KEYUP = 2

def release_all_keys():
    """모든 키 떼기"""
    key_up(VK_RIGHT)

def start_action(sender=None, app_data=None):
    """시작 버튼 동작"""
    global is_running
    if not is_running:
        is_running = True
        key_down(VK_RIGHT)
        update_button_states()

def stop_action(sender=None, app_data=None):
    """정지 버튼 동작"""
    global is_running
    is_running = False
    release_all_keys()
    update_button_states()

def update_button_states():
    """버튼 상태 업데이트"""
    try:
        if dpg.does_item_exist("start_button"):
            dpg.configure_item("start_button", enabled=not is_running)
        if dpg.does_item_exist("stop_button"):
            dpg.configure_item("stop_button", enabled=is_running)
    except:
        pass

def toggle_action():
    """F1 토글 동작"""
    global is_running
    if is_running:
        stop_action()
    else:
        start_action()

def hotkey_listener():
    """백그라운드 핫키 감지 스레드"""
    f1_pressed = False
    f2_pressed = False
    
    while True:
        # F1 감지
        f1_state = user32.GetAsyncKeyState(VK_F1) & 0x8000
        if f1_state and not f1_pressed:
            f1_pressed = True
            toggle_action()
        elif not f1_state:
            f1_pressed = False
        
        # F2 감지
        f2_state = user32.GetAsyncKeyState(VK_F2) & 0x8000
        if f2_state and not f2_pressed:
            f2_pressed = True
            stop_action()
        elif not f2_state:
            f2_pressed = False
        
        time.sleep(0.01)  # 10ms 간격

def setup_hotkeys():
    """핫키 리스너 시작"""
    thread = threading.Thread(target=hotkey_listener, daemon=True)
    thread.start()

def render_start_stop():
    """시작/정지 버튼 렌더링"""
    dpg.add_spacer(height=10)
    with dpg.group(horizontal=True):
        dpg.add_button(label="시작", tag="start_button", callback=start_action, width=80)
        dpg.add_button(label="정지", tag="stop_button", callback=stop_action, width=80, enabled=False)

# 핫키 설정 (모듈 로드 시 실행)
setup_hotkeys()
