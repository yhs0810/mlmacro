import dearpygui.dearpygui as dpg
from normal_setting import minimap

# 1층 Y 값 저장
floor_1_y = None

def set_floor_1(sender=None, app_data=None):
    """1층 Y 값 저장"""
    global floor_1_y
    pos = minimap.get_player_position()
    if pos:
        floor_1_y = pos[1]  # Y 값 저장

def get_current_floor():
    """현재 플레이어가 어느 층에 있는지 반환"""
    pos = minimap.get_player_position()
    if pos and floor_1_y is not None:
        current_y = pos[1]
        # ±4 오차 범위 내면 1층
        if abs(current_y - floor_1_y) <= 4:
            return 1
    return None

def render_floor_settings():
    """층 설정 UI 렌더링"""
    dpg.add_button(label="1층 지정", callback=set_floor_1, width=80)
    dpg.add_text("현재구역: -", tag="current_floor_text")

def update_floor_display():
    """현재 층 표시 업데이트"""
    if dpg.does_item_exist("current_floor_text"):
        floor = get_current_floor()
        if floor is not None:
            dpg.set_value("current_floor_text", f"현재구역: {floor}")
        else:
            dpg.set_value("current_floor_text", "현재구역: -")
