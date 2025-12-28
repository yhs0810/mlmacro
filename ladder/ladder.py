import dearpygui.dearpygui as dpg
from normal_setting import minimap
from floor import f_setting

# 사다리 데이터 저장 (13개 행)
ladder_data = []
for i in range(13):
    ladder_data.append({
        'left': False,
        'right': False,
        'zone': 0,
        'x': None,
        'y': None
    })

def on_left_change(sender, app_data, user_data):
    ladder_data[user_data]['left'] = app_data

def on_right_change(sender, app_data, user_data):
    ladder_data[user_data]['right'] = app_data

def on_zone_change(sender, app_data, user_data):
    try:
        ladder_data[user_data]['zone'] = int(app_data)
    except:
        pass

def set_zone(sender, app_data, user_data):
    """구역지정 - 입력된 구역 번호에 현재 Y값 저장"""
    # 사용자가 입력한 구역 번호 읽기
    zone_num = ladder_data[user_data]['zone']
    if zone_num >= 1 and zone_num <= 13:
        # 현재 Y좌표를 해당 구역에 저장
        pos = minimap.get_player_position()
        if pos:
            idx = zone_num - 1  # 0-indexed
            f_setting.zone_data[idx]['y'] = pos[1]
            # 버튼 레이블 업데이트 (Y: 123)
            dpg.configure_item(sender, label=f"Y: {pos[1]:.0f}")

def set_position(sender, app_data, user_data):
    """좌표지정"""
    pos = minimap.get_player_position()
    if pos:
        ladder_data[user_data]['x'] = pos[0]
        ladder_data[user_data]['y'] = pos[1]
        if dpg.does_item_exist(f"ladder_pos_{user_data}"):
            dpg.set_value(f"ladder_pos_{user_data}", f"({pos[0]:.0f},{pos[1]:.0f})")

def render_ladder_settings():
    """사다리 탭 렌더링"""
    dpg.add_text("[ 사다리 설정 ]")
    dpg.add_spacer(height=8)
    
    # 테이블 형식 (row_background=False로 모든 행 같은 색상)
    with dpg.table(header_row=True, borders_innerH=True, borders_outerH=True, 
                   borders_innerV=True, borders_outerV=True, row_background=False):
        
        dpg.add_table_column(label="#", width_fixed=True, init_width_or_weight=25)
        dpg.add_table_column(label="좌", width_fixed=True, init_width_or_weight=25)
        dpg.add_table_column(label="우", width_fixed=True, init_width_or_weight=25)
        dpg.add_table_column(label="구역", width_fixed=True, init_width_or_weight=50)
        dpg.add_table_column(label="구역지정", width_fixed=True, init_width_or_weight=60)
        dpg.add_table_column(label="좌표", width_fixed=True, init_width_or_weight=50)
        dpg.add_table_column(label="저장값", width_stretch=True)
        
        for i in range(13):
            with dpg.table_row():
                dpg.add_text(f"{i+1}")
                dpg.add_checkbox(tag=f"ladder_left_{i}", callback=on_left_change, user_data=i)
                dpg.add_checkbox(tag=f"ladder_right_{i}", callback=on_right_change, user_data=i)
                dpg.add_input_int(tag=f"ladder_zone_{i}", default_value=0, width=40, 
                                  callback=on_zone_change, user_data=i, step=0)
                dpg.add_button(label="지정", callback=set_zone, user_data=i, width=45)
                dpg.add_button(label="좌표", callback=set_position, user_data=i, width=40)
                dpg.add_text("(-,-)", tag=f"ladder_pos_{i}")

# 사다리 로직 실행
import ctypes
import time
import pydirectinput
from direction import check_direction

user32 = ctypes.windll.user32
VK_LEFT = 0x25
VK_RIGHT = 0x27

def safe_alt_press():
    """방향키 간섭 방지를 위해 방향키를 뗐다가 ALT 누르고 다시 누름"""
    left_pressed = check_direction.is_left_pressed()
    right_pressed = check_direction.is_right_pressed()
    
    # 방향키 떼기
    if left_pressed:
        user32.keybd_event(VK_LEFT, 0, 2, 0) # KeyUp
    if right_pressed:
        user32.keybd_event(VK_RIGHT, 0, 2, 0) # KeyUp
        
    time.sleep(0.02)
    
    # ALT 클릭 (pydirectinput 사용)
    pydirectinput.press('alt')
    
    time.sleep(0.02)
    
    # 방향키 복구
    if left_pressed:
        user32.keybd_event(VK_LEFT, 0, 0, 0) # KeyDown
    if right_pressed:
        user32.keybd_event(VK_RIGHT, 0, 0, 0) # KeyDown

import threading

# ... (existing imports)

def climb_routine(target_y):
    """ALT 누르고 목표 Y까지 UP 키 유지"""
    safe_alt_press()
    
    # 목표가 현재보다 위에 있는지 확인 (Y값이 더 작아야 함)
    pos = minimap.get_player_position()
    if not pos:
        return
        
    start_y = pos[1]
    
    # 목표가 위에 있을 때만 UP 키 지속
    if target_y < start_y:
        pydirectinput.keyDown('up')
        
        start_time = time.time()
        while True:
            # 매크로 정지 시 중단
            if not f_setting.is_running:
                break
                
            pos = minimap.get_player_position()
            if pos:
                current_y = pos[1]
                # 목표 높이 도달 확인 (오차 +2)
                if current_y <= target_y + 2:
                    break
            
            # 5초 타임아웃
            if time.time() - start_time > 5.0:
                break
            time.sleep(0.01)
            
        # 목표 도달 후 0.5초 더 유지
        time.sleep(0.5)
        pydirectinput.keyUp('up')

# 각 사다리 설정별 마지막 실행 시간 (쿨타임용)
ladder_cooldowns = [0] * 13

def update_ladder():
    """메인 루프에서 호출: 사다리 조건 확인 및 실행"""
    # 시작 상태가 아니면 실행하지 않음
    if not f_setting.is_running:
        return

    pos = minimap.get_player_position()
    if not pos:
        return
    
    current_x, current_y = pos
    current_time = time.time()
    
    for i in range(13):
        data = ladder_data[i]
        
        # 2. 좌표 설정 여부 확인
        if data['x'] is None or data['y'] is None:
            continue
            
        # 3. 좌표 범위 확인 (오차 0)
        if abs(current_x - data['x']) <= 0 and abs(current_y - data['y']) <= 0:
            
            # 4. 쿨타임 확인 (1초)
            if current_time - ladder_cooldowns[i] < 1.0:
                continue
                
            # 5. 방향키 조건 확인
            condition_met = False
            if data['left'] and data['right']:
                condition_met = True
            elif data['left']:
                if check_direction.is_left_pressed():
                    condition_met = True
            elif data['right']:
                if check_direction.is_right_pressed():
                    condition_met = True
            
            # 조건 만족 시 실행
            if condition_met:
                # 목표 구역의 Y값 가져오기
                target_y = None
                zone_idx = data['zone'] - 1
                if 0 <= zone_idx < 13:
                    target_y = f_setting.zone_data[zone_idx]['y']
                
                if target_y is not None:
                    # 스레드로 등반 실행
                    threading.Thread(target=climb_routine, args=(target_y,), daemon=True).start()
                else:
                    # 목표 Y 없으면 그냥 점프만
                    safe_alt_press()
                    
                ladder_cooldowns[i] = current_time
