import dearpygui.dearpygui as dpg
import ctypes
import threading
import time
from normal_setting import minimap

# Windows API
user32 = ctypes.windll.user32
VK_LEFT = 0x25
VK_RIGHT = 0x27
VK_F1 = 0x70
VK_F2 = 0x71

# 13개 구역 데이터
zone_data = []
for i in range(13):
    zone_data.append({
        'y': None,
        'left_x': 0,
        'right_x': 200
    })

# 시작 상태
is_running = False
current_direction = None

def key_down(vk_code):
    user32.keybd_event(vk_code, 0, 0, 0)

def key_up(vk_code):
    user32.keybd_event(vk_code, 0, 2, 0)

def set_zone_y(sender, app_data, user_data):
    """구역 Y값 저장"""
    pos = minimap.get_player_position()
    if pos:
        zone_data[user_data]['y'] = pos[1]

def on_left_x_change(sender, app_data, user_data):
    try:
        zone_data[user_data]['left_x'] = float(app_data)
    except:
        pass

def on_right_x_change(sender, app_data, user_data):
    try:
        zone_data[user_data]['right_x'] = float(app_data)
    except:
        pass

def start_macro(sender=None, app_data=None):
    global is_running, current_direction
    if not is_running:
        is_running = True
        key_down(VK_RIGHT)
        current_direction = 'right'

def stop_macro(sender=None, app_data=None):
    global is_running, current_direction
    is_running = False
    key_up(VK_LEFT)
    key_up(VK_RIGHT)
    current_direction = None

def toggle_macro():
    if is_running:
        stop_macro()
    else:
        start_macro()

last_valid_zone = None

def get_current_zone():
    """현재 플레이어가 어느 구역에 있는지 반환
    조건: Y값이 저장된 Y에서 -1 ~ +3 범위 내
          AND X값이 왼X ~ 오X 범위 내
    
    * 구역 유지 기능: 한 번 인식되면 다른 구역으로 인식될 때까지 유지
    """
    global last_valid_zone
    
    pos = minimap.get_player_position()
    if pos:
        current_x = pos[0]
        current_y = pos[1]
        for i in range(13):
            zone = zone_data[i]
            if zone['y'] is not None:
                # Y 오차: -1 ~ +3
                y_min = zone['y'] - 1
                y_max = zone['y'] + 3
                # X 범위 확인 (사용자가 반대로 입력했을 경우 대비)
                actual_left = min(zone['left_x'], zone['right_x'])
                actual_right = max(zone['left_x'], zone['right_x'])
                
                if y_min <= current_y <= y_max and actual_left <= current_x <= actual_right:
                    new_zone = i + 1
                    last_valid_zone = new_zone
                    return new_zone
    
    return last_valid_zone

# floor_1_y 호환성 유지
@property
def floor_1_y():
    return zone_data[0]['y']

@property
def floor_1_left_x():
    return zone_data[0]['left_x']

@property
def floor_1_right_x():
    return zone_data[0]['right_x']

def hotkey_listener():
    f1_pressed = False
    f2_pressed = False
    
    while True:
        f1_state = user32.GetAsyncKeyState(VK_F1) & 0x8000
        if f1_state and not f1_pressed:
            f1_pressed = True
            toggle_macro()
        elif not f1_state:
            f1_pressed = False
        
        f2_state = user32.GetAsyncKeyState(VK_F2) & 0x8000
        if f2_state and not f2_pressed:
            f2_pressed = True
            stop_macro()
        elif not f2_state:
            f2_pressed = False
        
        time.sleep(0.01)

def setup_hotkeys():
    thread = threading.Thread(target=hotkey_listener, daemon=True)
    thread.start()

def set_zone_1(sender=None, app_data=None):
    """1구역 Y값 저장"""
    pos = minimap.get_player_position()
    if pos:
        zone_data[0]['y'] = pos[1]

def render_floor_settings():
    """기본설정 탭: 현재 구역 표시 및 1구역 지정"""
    dpg.add_button(label="1구역지정", callback=set_zone_1, width=120, height=30)
    dpg.add_text("현재구역: -", tag="current_floor_text")

def render_zone_settings():
    """구역설정 탭: 13개 구역 설정 (X좌표만)"""
    with dpg.child_window(height=420, no_scrollbar=False):
        for i in range(13):
            dpg.add_text(f"[ {i+1}구역 설정 ]")
            with dpg.group(horizontal=True):
                dpg.add_text("왼 X:")
                dpg.add_input_float(tag=f"zone{i}_left_x", default_value=0, width=110, 
                                    callback=on_left_x_change, user_data=i, format="%.1f")
                dpg.add_text("오 X:")
                dpg.add_input_float(tag=f"zone{i}_right_x", default_value=200, width=110, 
                                    callback=on_right_x_change, user_data=i, format="%.1f")
            dpg.add_spacer(height=3)

def update_floor_display():
    """현재 구역 표시 및 자동 이동"""
    global current_direction
    
    zone = get_current_zone()
    if dpg.does_item_exist("current_floor_text"):
        if zone is not None:
            dpg.set_value("current_floor_text", f"현재구역: {zone}")
        else:
            dpg.set_value("current_floor_text", "현재구역: -")
    
    # 시작 상태일 때 자동 이동
    if is_running and zone is not None:
        pos = minimap.get_player_position()
        if pos:
            idx = zone - 1
            current_x = pos[0]
            left_x = zone_data[idx]['left_x']
            right_x = zone_data[idx]['right_x']
            
            if current_x <= left_x:
                if current_direction != 'right':
                    key_up(VK_LEFT)
                    key_down(VK_RIGHT)
                    current_direction = 'right'
            
            elif current_x >= right_x:
                if current_direction != 'left':
                    key_up(VK_RIGHT)
                    key_down(VK_LEFT)
                    current_direction = 'left'

# 핫키 설정
setup_hotkeys()
