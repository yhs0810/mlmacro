import dearpygui.dearpygui as dpg
import threading
import time

# 텔레포트 변수
current_teleport_key = None
teleport_delay = 0  # 0이면 비활성화
teleport_thread = None
teleport_running = False

# 텔레포트 블락 (공격 시)
teleport_block_on_attack = False
teleport_block_until = 0  # 이 시간까지 블락

# 선택 가능한 키 목록
available_keys = (
    [chr(i) for i in range(ord('A'), ord('Z') + 1)] +  # A-Z
    [str(i) for i in range(10)] +  # 0-9
    ['ctrl', 'shift']
)

def set_teleport_key(sender, app_data):
    global current_teleport_key
    current_teleport_key = app_data
    print(f"Teleport key set to: {current_teleport_key}")

def set_teleport_delay(sender, app_data):
    global teleport_delay
    try:
        teleport_delay = float(app_data)
    except:
        teleport_delay = 0
    print(f"Teleport delay set to: {teleport_delay}s")

def set_teleport_block_on_attack(sender, app_data):
    global teleport_block_on_attack
    teleport_block_on_attack = app_data
    print(f"Teleport block on attack: {teleport_block_on_attack}")

def trigger_teleport_block():
    """공격 시 텔레포트 블락 (0.5초), 중복 호출 시 리셋"""
    global teleport_block_until
    if teleport_block_on_attack:
        teleport_block_until = time.time() + 0.8

def teleport_loop():
    """텔레포트 키 주기적 입력 스레드"""
    global teleport_running
    
    import pydirectinput
    
    while teleport_running:
        try:
            # 매 루프마다 is_running 상태 확인
            from normal_setting import start_stop
            
            # 블락 체크
            is_blocked = time.time() < teleport_block_until
            
            # 시작 상태이고, 키가 설정되어 있고, 딜레이가 0보다 클 때만 작동
            if start_stop.is_running and current_teleport_key and teleport_delay > 0 and not is_blocked:
                key = current_teleport_key.lower()
                pydirectinput.press(key)
                print(f"Teleport: {key}")
            
            # 딜레이만큼 대기 (0이면 1초 대기)
            wait_time = teleport_delay if teleport_delay > 0 else 1
            time.sleep(wait_time)
            
        except Exception as e:
            print(f"Teleport loop error: {e}")
            time.sleep(1)

def start_teleport_thread():
    """텔레포트 스레드 시작"""
    global teleport_thread, teleport_running
    if teleport_thread is None or not teleport_thread.is_alive():
        teleport_running = True
        teleport_thread = threading.Thread(target=teleport_loop, daemon=True)
        teleport_thread.start()

def render_teleport_settings():
    """텔레포트 설정 UI 렌더링"""
    dpg.add_text("텔레포트 설정")
    
    with dpg.group(horizontal=True):
        dpg.add_text("텔레포트:")
        dpg.add_combo(items=available_keys, default_value="", width=100, callback=set_teleport_key)
        dpg.add_checkbox(label="몹 공격시 텔포블락", callback=set_teleport_block_on_attack)
    
    with dpg.group(horizontal=True):
        dpg.add_text("딜레이(초):")
        dpg.add_input_float(default_value=0, width=80, callback=set_teleport_delay, format="%.1f")
        
    dpg.add_text("※ 시작 상태일 때만 작동, 0이면 비활성화", color=[150, 150, 150])

# 스레드 자동 시작
start_teleport_thread()

