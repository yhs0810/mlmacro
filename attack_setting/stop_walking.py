import dearpygui.dearpygui as dpg
import threading
import time
import ctypes

# Windows API
user32 = ctypes.windll.user32
VK_LEFT = 0x25
VK_RIGHT = 0x27

# 멈추기 변수
stop_walking_on_attack = False
stop_walking_until = 0
last_direction_before_stop = None  # 'left' or 'right'
movement_thread = None
movement_running = False

def key_down(vk_code):
    user32.keybd_event(vk_code, 0, 0, 0)

def key_up(vk_code):
    user32.keybd_event(vk_code, 0, 2, 0)

def set_stop_walking_on_attack(sender, app_data):
    global stop_walking_on_attack
    stop_walking_on_attack = app_data
    print(f"Stop walking on attack: {stop_walking_on_attack}")

def trigger_stop_walking():
    """공격 시 이동 멈추기 (0.3초), 중복 호출 시 리셋"""
    global stop_walking_until, last_direction_before_stop
    
    if not stop_walking_on_attack:
        return
    
    # 현재 방향 저장 (처음 멈출 때만)
    if time.time() >= stop_walking_until:
        # 현재 방향 가져오기
        try:
            from floor import f_setting
            last_direction_before_stop = f_setting.current_direction
        except:
            last_direction_before_stop = 'right'
        
        # 방향키 떼기
        key_up(VK_LEFT)
        key_up(VK_RIGHT)
    
    # 타이머 리셋 (0.3초)
    stop_walking_until = time.time() + 0.6

def movement_restore_loop():
    """이동 복구 스레드"""
    global movement_running, last_direction_before_stop
    
    while movement_running:
        try:
            from normal_setting import start_stop
            from floor import f_setting
            
            # 멈춤 시간이 지났고, 복구 대상이 있으면 방향키 다시 누르기 (1회만)
            if stop_walking_on_attack and last_direction_before_stop:
                if time.time() >= stop_walking_until and start_stop.is_running:
                    if stop_walking_until > 0:  # 한 번이라도 멈춘 적이 있다면
                        # 현재 f_setting의 방향으로 복구 (바뀌었을 수 있음)
                        current_dir = f_setting.current_direction
                        if current_dir == 'left':
                            key_down(VK_LEFT)
                        else:
                            key_down(VK_RIGHT)
                        
                        # 복구 완료 - 플래그 클리어 (중복 실행 방지)
                        last_direction_before_stop = None
            
            time.sleep(0.05)
            
        except Exception as e:
            print(f"Movement restore error: {e}")
            time.sleep(1)

def start_movement_thread():
    """이동 복구 스레드 시작"""
    global movement_thread, movement_running
    if movement_thread is None or not movement_thread.is_alive():
        movement_running = True
        movement_thread = threading.Thread(target=movement_restore_loop, daemon=True)
        movement_thread.start()

def render_stop_walking_settings():
    """몹 공격시 멈추기 설정 UI 렌더링"""
    with dpg.group(horizontal=True):
        dpg.add_checkbox(label="몹 공격시 멈추기", callback=set_stop_walking_on_attack)
        dpg.add_text("(0.3초 동안 방향키 떼기)", color=[150, 150, 150])

# 스레드 자동 시작
start_movement_thread()
