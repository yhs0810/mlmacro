import dearpygui.dearpygui as dpg
import os
import ctypes
import threading
import time

from normal_setting.minimap import render_minimap_settings, update_minimap, get_player_position, create_minimap_window, toggle_minimap
from normal_setting.player_x_y import render_player_xy, update_player_xy
from floor.first_f import render_floor_settings, update_floor_display

# M키 핫키 감지
user32 = ctypes.windll.user32
VK_M = 0x4D

def m_key_listener():
    m_pressed = False
    while True:
        m_state = user32.GetAsyncKeyState(VK_M) & 0x8000
        if m_state and not m_pressed:
            m_pressed = True
            toggle_minimap()
        elif not m_state:
            m_pressed = False
        time.sleep(0.01)

# M키 리스너 시작
threading.Thread(target=m_key_listener, daemon=True).start()

dpg.create_context()

# 뷰포트 생성 (넓게 설정하여 미니맵 창도 표시 가능)
dpg.create_viewport(title='Maple Land Macro', width=750, height=500)

# 한글 폰트 설정 (깨짐 방지)
with dpg.font_registry():
    font_path = "C:/Windows/Fonts/malgun.ttf"
    if os.path.exists(font_path):
        with dpg.font(font_path, 18) as default_font:
            dpg.add_font_range_hint(dpg.mvFontRangeHint_Korean)
        dpg.bind_font(default_font)

# 메인 윈도우 생성 (스크롤바 제거)
with dpg.window(label="Main Window", width=500, height=500, no_resize=True, no_move=True, no_collapse=True, no_title_bar=True, no_scrollbar=True):
    with dpg.tab_bar():
        with dpg.tab(label="기본설정"):
            render_minimap_settings()
            render_player_xy()
            render_floor_settings()
        with dpg.tab(label="공격설정"):
            dpg.add_text("공격설정 탭입니다.")

# 미니맵 윈도우 생성 (별도 창)
create_minimap_window()

dpg.setup_dearpygui()
dpg.show_viewport()

# 메인 루프 (실시간 업데이트)
while dpg.is_dearpygui_running():
    update_minimap()
    update_player_xy()
    update_floor_display()
    dpg.render_dearpygui_frame()

dpg.destroy_context()
