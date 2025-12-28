import dearpygui.dearpygui as dpg
import threading
import time

# 공격 키 변수 (기본값 None)
current_attack_key = None

# 계속 공격하기 옵션
continuous_attack = False
attack_thread = None
attack_running = False

# 선택 가능한 키 목록
available_keys = [chr(i) for i in range(ord('A'), ord('Z') + 1)] + [str(i) for i in range(10)]

def set_attack_key(sender, app_data):
    global current_attack_key
    current_attack_key = app_data
    print(f"Attack key set to: {current_attack_key}")

def set_continuous_attack(sender, app_data):
    global continuous_attack
    continuous_attack = app_data
    print(f"Continuous attack: {continuous_attack}")

def attack_loop():
    """계속 공격하기 스레드"""
    global attack_running
    
    import pydirectinput
    
    while attack_running:
        try:
            from normal_setting import start_stop
            
            # 시작 상태이고, 계속 공격이 활성화되어 있고, 키가 설정된 경우
            if start_stop.is_running and continuous_attack and current_attack_key:
                key = current_attack_key.lower()
                pydirectinput.press(key)
            
            time.sleep(0.05)  # 초당 약 20회 공격
            
        except Exception as e:
            print(f"Attack loop error: {e}")
            time.sleep(1)

def start_attack_thread():
    """공격 스레드 시작"""
    global attack_thread, attack_running
    if attack_thread is None or not attack_thread.is_alive():
        attack_running = True
        attack_thread = threading.Thread(target=attack_loop, daemon=True)
        attack_thread.start()

def render_attack_key_settings():
    """공격 키 설정 UI 렌더링"""
    dpg.add_text("공격 키 설정")
    
    with dpg.group(horizontal=True):
        dpg.add_text("공격 키:")
        dpg.add_combo(items=available_keys, default_value="", width=100, callback=set_attack_key)
        dpg.add_checkbox(label="계속 공격하기", callback=set_continuous_attack)
        
    dpg.add_text("※ 체크 시 몬스터 감지와 무관하게 계속 공격합니다.", color=[150, 150, 150])

# 스레드 자동 시작
start_attack_thread()
