import dearpygui.dearpygui as dpg
from normal_setting import minimap

def render_player_xy():
    """캔버스 아래에 플레이어 X, Y 좌표 표시"""
    dpg.add_text("X: 0  Y: 0", tag="player_xy_text")

def update_player_xy():
    """실시간으로 플레이어 좌표 업데이트"""
    if dpg.does_item_exist("player_xy_text"):
        pos = minimap.get_player_position()
        if pos:
            dpg.set_value("player_xy_text", f"X: {pos[0]:.1f}  Y: {pos[1]:.1f}")
        else:
            dpg.set_value("player_xy_text", "X: -  Y: -")
