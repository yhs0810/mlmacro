import dearpygui.dearpygui as dpg
import os

from normal_setting.minimap import render_minimap_settings, update_minimap

dpg.create_context()

# 뷰포트 생성 (전체 창 크기 설정)
dpg.create_viewport(title='Maple Land Macro', width=500, height=500)

# 한글 폰트 설정 (깨짐 방지)
with dpg.font_registry():
    # 윈도우 기본 폰트 경로 시도
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
        with dpg.tab(label="공격설정"):
            dpg.add_text("공격설정 탭입니다.")

dpg.setup_dearpygui()
dpg.show_viewport()

# 메인 루프 (실시간 업데이트)
while dpg.is_dearpygui_running():
    update_minimap()
    dpg.render_dearpygui_frame()

dpg.destroy_context()
