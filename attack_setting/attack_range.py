import dearpygui.dearpygui as dpg

# 공격 범위 변수 (기본값 100)
attack_range_x = 100
attack_range_y = 100

def set_attack_range_x(sender, app_data):
    global attack_range_x
    attack_range_x = app_data

def set_attack_range_y(sender, app_data):
    global attack_range_y
    attack_range_y = app_data

def render_attack_settings():
    """공격 설정 탭 UI 렌더링"""
    dpg.add_text("공격 범위 설정 (IGN 기준)")
    
    with dpg.group(horizontal=True):
        dpg.add_text("X 범위(±):")
        dpg.add_input_int(default_value=attack_range_x, width=100, callback=set_attack_range_x, min_value=0, max_value=1000)
        
    with dpg.group(horizontal=True):
        dpg.add_text("Y 범위(±):")
        dpg.add_input_int(default_value=attack_range_y, width=100, callback=set_attack_range_y, min_value=0, max_value=1000)
    
    dpg.add_text("※ IGN 중앙을 기준으로 설정한 범위만큼 박스가 표시됩니다.", color=[150, 150, 150])
