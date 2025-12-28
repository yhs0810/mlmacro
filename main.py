import dearpygui.dearpygui as dpg
import os
import ctypes
import threading
import time

from normal_setting.minimap import render_minimap_settings, update_minimap, get_player_position, create_minimap_window, toggle_minimap
from normal_setting.player_x_y import render_player_xy, update_player_xy
from floor.f_setting import render_floor_settings, update_floor_display, render_zone_settings
from ladder.ladder import render_ladder_settings, update_ladder
from jump_down.j_d import render_jump_down_settings, update_jump_down
from training_area.training_area import render_training_area, update_mob_area, create_mob_window, toggle_mob_window
from normal_setting.ign_capture import render_ign_capture
from normal_setting.monster_capture import render_monster_capture
from attack_setting.attack_range import render_attack_settings

# M키, T키 핫키 감지
user32 = ctypes.windll.user32
VK_M = 0x4D
VK_T = 0x54

def hotkey_listener():
    """핫키 감지 리스너"""
    m_pressed = False
    t_pressed = False
    
    while True:
        # M키 (미니맵)
        m_state = user32.GetAsyncKeyState(VK_M) & 0x8000
        if m_state and not m_pressed:
            m_pressed = True
            toggle_minimap()
        elif not m_state:
            m_pressed = False
            
        # T키 (몹 감지 구역)
        t_state = user32.GetAsyncKeyState(VK_T) & 0x8000
        if t_state and not t_pressed:
            t_pressed = True
            toggle_mob_window()
        elif not t_state:
            t_pressed = False
            
        time.sleep(0.01)

# 핫키 리스너 시작
threading.Thread(target=hotkey_listener, daemon=True).start()

dpg.create_context()

# 뷰포트 생성 (넓게 설정하여 미니맵 창도 표시 가능)
dpg.create_viewport(title='Maple Land Macro', width=750, height=520, vsync=False)

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
            dpg.add_spacer(height=10)
            
            # 1행: 미니맵 관련
            with dpg.group(horizontal=True):
                render_minimap_settings()
                dpg.add_spacer(width=20)
                render_training_area() # 몹감지구역
            
            dpg.add_spacer(height=10)
            
            # 2행: 캡처 관련
            with dpg.group(horizontal=True):
                render_ign_capture() # 닉네임 캡쳐
                dpg.add_spacer(width=20)
                render_monster_capture() # 몬스터 캡쳐
            
            dpg.add_spacer(height=10)
            dpg.add_separator()
            dpg.add_spacer(height=10)
            
            # 3행: 좌표 및 구역 정보
            render_player_xy()
            dpg.add_spacer(height=5)
            render_floor_settings() # 1구역지정 및 현재구역 표시
        with dpg.tab(label="구역설정"):
            render_zone_settings()
        with dpg.tab(label="공격설정"):
            render_attack_settings()
        with dpg.tab(label="사다리"):
            render_ladder_settings()
        with dpg.tab(label="점프다운"):
            render_jump_down_settings()

# 미니맵 윈도우 생성 (별도 창)
create_minimap_window()
# 몹 감지 윈도우 생성
create_mob_window()

dpg.setup_dearpygui()
dpg.show_viewport()

# 메인 루프 (실시간 업데이트)
while dpg.is_dearpygui_running():
    update_minimap()
    update_mob_area()
    update_player_xy()
    update_floor_display()
    update_ladder()
    update_jump_down()
    dpg.render_dearpygui_frame()

dpg.destroy_context()
