import dearpygui.dearpygui as dpg
import ctypes
import time

# Windows API
user32 = ctypes.windll.user32
VK_LEFT = 0x25
VK_RIGHT = 0x27

# 뒷 몹감지 변수
behind_mob_detection = False

def key_down(vk_code):
    user32.keybd_event(vk_code, 0, 0, 0)

def key_up(vk_code):
    user32.keybd_event(vk_code, 0, 2, 0)

def set_behind_mob_detection(sender, app_data):
    global behind_mob_detection
    behind_mob_detection = app_data
    print(f"Behind mob detection: {behind_mob_detection}")

def check_and_turn_for_behind_mob(monsters_in_attack_box, ign_center_x, current_direction):
    """
    뒤에 있는 몹만 있으면 뒤로 돌기
    
    monsters_in_attack_box: 공격 범위 내 몬스터 좌표 리스트 [(x, y), ...]
    ign_center_x: IGN 중심의 X 좌표
    current_direction: 현재 방향 'left' or 'right'
    
    Returns: True if turned, False otherwise
    """
    if not behind_mob_detection:
        return False
    
    if not monsters_in_attack_box or not current_direction:
        return False
    
    # 몬스터들을 IGN 기준으로 왼쪽/오른쪽으로 분류
    monsters_left = []   # IGN보다 왼쪽 (x < ign_center_x)
    monsters_right = []  # IGN보다 오른쪽 (x > ign_center_x)
    
    for mx, my in monsters_in_attack_box:
        if mx < ign_center_x:
            monsters_left.append((mx, my))
        elif mx > ign_center_x:
            monsters_right.append((mx, my))
    
    # 오른쪽으로 이동 중인데, 왼쪽에만 몹이 있고 오른쪽에는 없음
    if current_direction == 'right':
        if len(monsters_left) > 0 and len(monsters_right) == 0:
            # 뒤로 돌기: 오른쪽 떼고 왼쪽 누르기 (별도 스레드)
            def turn_left_action():
                try:
                    from floor import f_setting
                    key_up(VK_LEFT)
                    key_up(VK_RIGHT)
                    time.sleep(0.01)
                    key_down(VK_LEFT)
                    f_setting.current_direction = 'left'
                    print("Behind mob: Turned LEFT")
                except: pass
            
            import threading
            threading.Thread(target=turn_left_action, daemon=True).start()
            return True
    
    # 왼쪽으로 이동 중인데, 오른쪽에만 몹이 있고 왼쪽에는 없음
    elif current_direction == 'left':
        if len(monsters_right) > 0 and len(monsters_left) == 0:
            # 뒤로 돌기: 왼쪽 떼고 오른쪽 누르기 (별도 스레드)
            def turn_right_action():
                try:
                    from floor import f_setting
                    key_up(VK_LEFT)
                    key_up(VK_RIGHT)
                    time.sleep(0.01)
                    key_down(VK_RIGHT)
                    f_setting.current_direction = 'right'
                    print("Behind mob: Turned RIGHT")
                except: pass
            
            import threading
            threading.Thread(target=turn_right_action, daemon=True).start()
            return True
    
    return False

def render_behind_mob_settings():
    """뒷 몹감지 설정 UI 렌더링"""
    with dpg.group(horizontal=True):
        dpg.add_checkbox(label="뒷 몹감지", callback=set_behind_mob_detection)
        dpg.add_text("(뒤에만 몹 있으면 뒤로 돌기)", color=[150, 150, 150])
