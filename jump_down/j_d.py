import dearpygui.dearpygui as dpg
from normal_setting import minimap
from floor import f_setting
import time
import threading
import pydirectinput
import ctypes
from direction import check_direction

# 점프다운 데이터 저장 (13개 행)
jump_down_data = []
for i in range(13):
    jump_down_data.append({
        'left': False,
        'right': False,
        'repeat_sec': 1.0,
        'x': None,
        'y': None,
        'ignore_count': 0,
        'current_ignore': 0,  # 현재 무시한 횟수 카운트
        'is_active': False    # 현재 동작 실행 중인지 여부
    })

# 콜백 함수들
def on_left_change(sender, app_data, user_data):
    jump_down_data[user_data]['left'] = app_data

def on_right_change(sender, app_data, user_data):
    jump_down_data[user_data]['right'] = app_data

def on_repeat_change(sender, app_data, user_data):
    try:
        val = float(app_data)
        if val < 0: val = 0
        jump_down_data[user_data]['repeat_sec'] = val
    except:
        pass

def on_ignore_change(sender, app_data, user_data):
    try:
        val = int(app_data)
        if val < 0: val = 0
        jump_down_data[user_data]['ignore_count'] = val
        jump_down_data[user_data]['current_ignore'] = 0 # 설정 변경 시 카운트 초기화
    except:
        pass

def set_position(sender, app_data, user_data):
    """좌표지정"""
    pos = minimap.get_player_position()
    if pos:
        jump_down_data[user_data]['x'] = pos[0]
        jump_down_data[user_data]['y'] = pos[1]
        if dpg.does_item_exist(f"jd_pos_{user_data}"):
            dpg.set_value(f"jd_pos_{user_data}", f"({pos[0]:.0f},{pos[1]:.0f})")

def render_jump_down_settings():
    """점프다운 탭 렌더링"""
    dpg.add_text("[ 점프다운 설정 ]")
    dpg.add_spacer(height=8)
    
    # 테이블 형식
    with dpg.table(header_row=True, borders_innerH=True, borders_outerH=True, 
                   borders_innerV=True, borders_outerV=True, row_background=False):
        
        dpg.add_table_column(label="#", width_fixed=True, init_width_or_weight=25)
        dpg.add_table_column(label="좌", width_fixed=True, init_width_or_weight=25)
        dpg.add_table_column(label="우", width_fixed=True, init_width_or_weight=25)
        dpg.add_table_column(label="반복(초)", width_fixed=True, init_width_or_weight=50)
        dpg.add_table_column(label="좌표", width_fixed=True, init_width_or_weight=40)
        dpg.add_table_column(label="무시횟수", width_fixed=True, init_width_or_weight=65)
        dpg.add_table_column(label="저장값", width_stretch=True)
        
        for i in range(13):
            with dpg.table_row():
                dpg.add_text(f"{i+1}")
                dpg.add_checkbox(tag=f"jd_left_{i}", callback=on_left_change, user_data=i)
                dpg.add_checkbox(tag=f"jd_right_{i}", callback=on_right_change, user_data=i)
                dpg.add_input_float(tag=f"jd_repeat_{i}", default_value=1.0, width=70, step=0, format="%.1f",
                                    callback=on_repeat_change, user_data=i)
                dpg.add_button(label="좌표", callback=set_position, user_data=i, width=40)
                dpg.add_input_int(tag=f"jd_ignore_{i}", default_value=0, width=70, step=0,
                                  callback=on_ignore_change, user_data=i)
                dpg.add_text("(-,-)", tag=f"jd_pos_{i}")

# 로직 실행
user32 = ctypes.windll.user32
VK_DOWN = 0x28

def jump_down_routine(index, duration):
    """ALT+DOWN 반복 수행 루틴"""
    jump_down_data[index]['is_active'] = True
    print(f"Jump Down triggered for row {index+1}, duration: {duration}s")
    
    start_time = time.time()
    
    # DOWN 키 누름 유지
    pydirectinput.keyDown('down')
    time.sleep(0.05)
    
    while time.time() - start_time < duration:
        if not f_setting.is_running:
            break
            
        # ALT 반복 클릭
        pydirectinput.press('alt')
        time.sleep(0.1) # 너무 빠르지 않게 조절
        
    pydirectinput.keyUp('down')
    jump_down_data[index]['is_active'] = False
    # 동작 종료 시점 기록 (쿨타임 시작)
    jd_cooldowns[index] = time.time()

# 쿨타임 (중복 실행 방지용, 동작 시간보다 길어야 함)
jd_cooldowns = [0] * 13

def update_jump_down():
    """메인 루프에서 호출"""
    if not f_setting.is_running:
        return

    pos = minimap.get_player_position()
    if not pos:
        return
    
    current_x, current_y = pos
    current_time = time.time()
    
    for i in range(13):
        data = jump_down_data[i]
        
        # 이미 동작 중이면 스킵
        if data['is_active']:
            continue
            
        # 쿨타임 체크 (동작 종료 후 2초 대기)
        if current_time - jd_cooldowns[i] < 2.0:
            continue
            
        # 좌표 설정 확인
        if data['x'] is None or data['y'] is None:
            continue
            
        # 좌표 일치 확인 (오차 0)
        if abs(current_x - data['x']) <= 0 and abs(current_y - data['y']) <= 0:
            
            # 방향키 조건 확인
            condition_met = False
            if data['left'] and data['right']:
                condition_met = True
            elif data['left']:
                if check_direction.is_left_pressed():
                    condition_met = True
            elif data['right']:
                if check_direction.is_right_pressed():
                    condition_met = True
            
            if condition_met:
                # 무시 횟수 체크
                if data['current_ignore'] < data['ignore_count']:
                    data['current_ignore'] += 1
                    print(f"Jump Down ignored for row {i+1} ({data['current_ignore']}/{data['ignore_count']})")
                    # 쿨타임만 갱신하여 바로 다시 체크되지 않도록 함 (잠시 대기)
                    jd_cooldowns[i] = current_time
                    continue
                
                # 발동 조건 만족 -> 실행 및 카운트 초기화
                data['current_ignore'] = 0
                # 쿨타임은 루틴 종료 시 설정됨
                
                # 스레드로 동작 실행
                threading.Thread(target=jump_down_routine, args=(i, data['repeat_sec']), daemon=True).start()
