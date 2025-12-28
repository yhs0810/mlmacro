import dearpygui.dearpygui as dpg
import mss
import numpy as np
import cv2
import threading
import os
import time
import ctypes
import glob
from normal_setting.minimap import AreaSelector

# mss 인스턴스 (메인 스레드에서 공유하거나 별도 생성)
sct = mss.mss()
monitor = sct.monitors[1]

# 몹 감지 구역 상태
mob_selected_region = None  # {top, left, width, height}
is_mob_window_open = True
current_mob_texture_tag = "mob_texture" # 현재 사용 중인 텍스처 태그

# 텍스처 데이터 초기화 (고정 크기 200x120)
mob_texture_width = 200
mob_texture_height = 120
mob_texture_data = np.zeros((mob_texture_height, mob_texture_width, 4), dtype=np.float32)

# 스레드 제어 변수
capture_thread = None
capture_running = False
latest_frame = None
frame_lock = threading.Lock()

# DPG 그리기용 공유 변수
detected_monsters_for_draw = [] # [(x, y), ...]
ign_box_for_draw = None # (x1, y1, x2, y2) or None
attack_box_for_draw = None # (x1, y1, x2, y2) or None
draw_data_lock = threading.Lock()

# IGN 템플릿
ign_template = None
ign_template_path = "tools/ign/ign.png"

# 몬스터 템플릿 목록 (원본 및 축소본)
monster_templates = []
monster_templates_small = []  # 0.5배 축소본
monster_template_dir = "tools/monster"

def load_ign_template():
    """IGN 템플릿 로드"""
    global ign_template
    if os.path.exists(ign_template_path):
        try:
            # 한글 경로 지원을 위해 numpy로 읽기
            img_array = np.fromfile(ign_template_path, np.uint8)
            ign_template = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            print("IGN template loaded.")
        except Exception as e:
            print(f"Failed to load IGN template: {e}")
            ign_template = None
    else:
        ign_template = None

def load_monster_templates():
    """몬스터 템플릿 로드 (원본 및 0.5배 축소본 생성)"""
    global monster_templates, monster_templates_small
    monster_templates = []
    monster_templates_small = []
    
    if not os.path.exists(monster_template_dir):
        return
        
    files = glob.glob(os.path.join(monster_template_dir, "monster*.png"))
    for f in files:
        try:
            img_array = np.fromfile(f, np.uint8)
            tmpl = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if tmpl is not None:
                monster_templates.append(tmpl)
                # 0.5배 축소본 생성 (속도 최적화용)
                tmpl_small = cv2.resize(tmpl, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
                monster_templates_small.append(tmpl_small)
        except Exception as e:
            print(f"Failed to load monster template {f}: {e}")
    print(f"Loaded {len(monster_templates)} monster templates (and small versions).")

# 초기 로드 시도
load_ign_template()
load_monster_templates()

import concurrent.futures

# OpenCL 사용 설정 (GPU 가속 시도)
try:
    cv2.ocl.setUseOpenCL(True)
except:
    pass

def process_template_batch(img_bgr, templates):
    """템플릿 배치를 처리하여 결과 좌표 반환 (CPU 매칭 + GPU 좌표 계산)"""
    results = []
    
    try:
        # 입력 이미지 0.5배 축소
        img_small = cv2.resize(img_bgr, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_LINEAR)
        
        for tmpl_small in templates:
            try:
                # 1. CPU 매칭 수행 (numpy 배열 사용)
                res = cv2.matchTemplate(img_small, tmpl_small, cv2.TM_CCOEFF_NORMED)
                
                # 2. GPU 좌표 계산 (UMat 변환)
                # 결과를 GPU 메모리로 업로드
                res_umat = cv2.UMat(res)
                
                # GPU에서 임계값 적용 (0.99 이상만 255로, 나머지는 0)
                _, thresh_umat = cv2.threshold(res_umat, 0.99, 255, cv2.THRESH_BINARY)
                
                # GPU에서 0이 아닌 좌표 찾기
                loc_umat = cv2.findNonZero(thresh_umat)
                
                # 결과를 CPU로 다운로드 (있을 경우에만)
                if loc_umat is not None:
                    loc = loc_umat.get()
                    
                    # loc은 (N, 1, 2) 형태, (x, y) 좌표
                    for pt in loc:
                        x, y = pt[0]
                        # 좌표를 다시 2배로 확대하여 원본 좌표로 복원
                        center_x = int((x + tmpl_small.shape[1] // 2) * 2)
                        center_y = int((y + tmpl_small.shape[0] // 2) * 2)
                        results.append((center_x, center_y))
            except:
                pass
    except Exception as e:
        print(f"Hybrid processing error: {e}")
        
    return results

def capture_loop():
    """고속 캡처 및 병렬 처리 루프 (별도 스레드)"""
    global latest_frame, capture_running, ign_template, monster_templates
    
    # 스레드 풀 생성 (최대 작업자 수 조절 가능)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    
    target_fps = 100
    frame_time = 1.0 / target_fps
    
    with mss.mss() as sct_thread:
        while capture_running:
            start_time = time.time()
            
            if mob_selected_region is None:
                time.sleep(0.1)
                continue
                
            try:
                # 1. 캡처
                raw = sct_thread.grab(mob_selected_region)
                img = np.array(raw)
                img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # 2. 병렬 처리 (몬스터 추적) 시작
                detected_points = []
                futures = []
                
                # 몬스터 템플릿을 5개씩 묶어서 처리
                # 2. 몬스터 감지 (병렬 처리) - 축소된 템플릿 사용
                batch_size = 5
                if monster_templates_small:
                    for i in range(0, len(monster_templates_small), batch_size):
                        batch = monster_templates_small[i:i + batch_size]
                        futures.append(executor.submit(process_template_batch, img_bgr, batch))
                
                # 3. IGN 추적 및 공격 범위 계산
                attack_box = None
                local_ign_box = None
                local_attack_box = None
                
                if ign_template is not None:
                    try:
                        res = cv2.matchTemplate(img_bgr, ign_template, cv2.TM_CCOEFF_NORMED)
                        threshold = 0.8
                        loc = np.where(res >= threshold)
                        h, w = ign_template.shape[:2]
                        for pt in zip(*loc[::-1]):
                            # IGN 박스 좌표 저장 (그리기는 update_mob_area에서)
                            local_ign_box = (pt[0], pt[1], pt[0] + w, pt[1] + h)
                            
                            # 공격 범위 박스 계산
                            try:
                                from attack_setting.attack_range import attack_range_x, attack_range_y
                                center_x = pt[0] + w // 2
                                center_y = pt[1] + h // 2
                                
                                x1 = center_x - attack_range_x
                                y1 = center_y - attack_range_y
                                x2 = center_x + attack_range_x
                                y2 = center_y + attack_range_y
                                
                                attack_box = (x1, y1, x2, y2)
                                local_attack_box = attack_box
                            except: pass
                    except: pass
                
                # 4. 몬스터 감지 결과 수집
                for future in concurrent.futures.as_completed(futures):
                    try:
                        points = future.result()
                        detected_points.extend(points)
                    except: pass
                
                # 5. 몬스터 리스트 관리 및 공격 판정
                from normal_setting.start_stop import is_running, key_down, key_up
                from attack_setting.attack_key_setting import current_attack_key
                
                # 몬스터 점 즉시 표시/제거 (잔상 없음, 중복 제거)
                current_monsters = list(set((pt[0], pt[1]) for pt in detected_points))
                
                # 최대 50개 제한
                if len(current_monsters) > 50:
                    current_monsters = current_monsters[-50:]
                
                # DPG 그리기용 좌표 저장
                with draw_data_lock:
                    global detected_monsters_for_draw, ign_box_for_draw, attack_box_for_draw
                    detected_monsters_for_draw = current_monsters
                    ign_box_for_draw = local_ign_box
                    attack_box_for_draw = local_attack_box
                
                # 공격 판정
                attack_triggered_this_frame = False
                monsters_in_attack_box = []  # 공격 범위 내 몬스터
                
                for mx, my in current_monsters:
                    # 공격 범위 내에 몬스터가 있고, 매크로가 실행 중이며, 공격 키가 설정된 경우
                    if attack_box and is_running and current_attack_key:
                        x1, y1, x2, y2 = attack_box
                        if x1 <= mx <= x2 and y1 <= my <= y2:
                            attack_triggered_this_frame = True
                            monsters_in_attack_box.append((mx, my))
                
                # 뒷 몹감지 체크 (공격 범위 내 몬스터가 있을 때)
                if is_running and local_ign_box and len(monsters_in_attack_box) > 0:
                    try:
                        from attack_setting.behind_mob import check_and_turn_for_behind_mob
                        from floor import f_setting
                        
                        # IGN 중심 X 좌표 계산
                        ign_center_x = (local_ign_box[0] + local_ign_box[2]) // 2
                        
                        # 뒤에만 몹 있으면 뒤로 돌기
                        check_and_turn_for_behind_mob(
                            monsters_in_attack_box, 
                            ign_center_x, 
                            f_setting.current_direction
                        )
                    except: pass
                
                # 공격 실행 (이동 제어 없음 - 방향키 계속 누름)
                if attack_triggered_this_frame:
                    # 경계 벗어남 확인 (공격 방지)
                    try:
                        from floor.f_setting import get_current_zone, zone_data
                        from normal_setting.minimap import get_player_position
                        
                        zone_idx = get_current_zone()
                        if zone_idx:
                            pos = get_player_position()
                            if pos:
                                idx = zone_idx - 1
                                cx = pos[0]
                                lx = zone_data[idx]['left_x']
                                rx = zone_data[idx]['right_x']
                                
                                # 경계를 벗어났다면 공격하지 않음
                                if cx < lx or cx > rx:
                                    attack_triggered_this_frame = False
                    except: pass
                
                if attack_triggered_this_frame:
                    # 공격 관련 트리거 호출
                    try:
                        from attack_setting.tele_port import trigger_teleport_block
                        from attack_setting.stop_walking import trigger_stop_walking
                        trigger_teleport_block()
                        trigger_stop_walking()
                    except: pass
                    
                    # 공격 키 누르기 (쿨타임 없음, 홀드 없음, 별도 스레드)
                    def attack_action():
                        try:
                            import pydirectinput
                            key = current_attack_key.lower()
                            pydirectinput.press(key)
                        except: pass
                    
                    import threading
                    threading.Thread(target=attack_action, daemon=True).start()
                
                # 6. 결과 저장
                with frame_lock:
                    latest_frame = img
                
                # FPS 제한 (100 FPS)
                elapsed = time.time() - start_time
                sleep_time = frame_time - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
            except Exception as e:
                print(f"Capture thread error: {e}")
                time.sleep(1)

def start_capture_thread():
    """캡처 스레드 시작"""
    global capture_thread, capture_running
    if capture_thread is None or not capture_thread.is_alive():
        print("Starting capture thread...")
        capture_running = True
        capture_thread = threading.Thread(target=capture_loop, daemon=True)
        capture_thread.start()
    else:
        print("Capture thread already running.")

def select_mob_area(sender, app_data, user_data):
    """몹 감지 구역 선택"""
    global mob_selected_region
    
    selector = AreaSelector()
    region = selector.get_region()
    
    if region:
        print(f"Mob area selected: {region}")
        mob_selected_region = region
        # 캡처 스레드 시작 (이미 돌고 있으면 무시됨)
        start_capture_thread()

def create_mob_window():
    """몹 감지 확인용 윈도우 생성"""
    global current_mob_texture_tag
    
    if not dpg.does_item_exist("mob_texture_registry"):
        with dpg.texture_registry(tag="mob_texture_registry"):
            dpg.add_dynamic_texture(width=mob_texture_width, height=mob_texture_height, default_value=mob_texture_data, tag=current_mob_texture_tag)
            
    # 위치: 미니맵(510, 10, h=200) 아래 -> [510, 220]
    # 윈도우 크기 고정 (200x120 이미지 + 여백)
    with dpg.window(label="몹 감지 구역", tag="mob_window", width=220, height=160, 
                    no_scrollbar=True, show=True, pos=[510, 220]):
        with dpg.drawlist(width=mob_texture_width, height=mob_texture_height, tag="mob_drawlist"):
            dpg.draw_image(current_mob_texture_tag, [0, 0], [mob_texture_width, mob_texture_height], tag="mob_image")
        
        # 좌표 텍스트 추가
        with dpg.group(horizontal=True):
            dpg.add_text("X: - | Y: -", tag="mob_xy_text")
            dpg.add_spacer(width=20)
            dpg.add_text("FPS: 0", tag="mob_fps_text", color=[0, 255, 0])

# FPS 계산 변수
last_time = time.time()
frame_count = 0
current_fps = 0

def update_mob_area():
    """몹 감지 구역 실시간 업데이트 (메인 스레드 - 렌더링만 담당)"""
    global mob_texture_data, current_mob_texture_tag, latest_frame
    global last_time, frame_count, current_fps
    
    # FPS 계산
    current_time = time.time()
    frame_count += 1
    if current_time - last_time >= 1.0:
        current_fps = frame_count
        frame_count = 0
        last_time = current_time
        if dpg.does_item_exist("mob_fps_text"):
            dpg.set_value("mob_fps_text", f"FPS: {current_fps}")

    if not is_mob_window_open or mob_selected_region is None:
        return

    try:
        # 최신 프레임 가져오기 (이미 처리된 이미지)
        img = None
        with frame_lock:
            if latest_frame is not None:
                img = latest_frame.copy()
        
        if img is None:
            return

        # BGRA -> RGBA 변환 (표시용)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
        
        # 크기 조정 (200x120) - cv2.INTER_NEAREST가 더 빠름
        img = cv2.resize(img, (mob_texture_width, mob_texture_height), interpolation=cv2.INTER_NEAREST)
        
        # float32로 변환 및 정규화
        data = img.astype(np.float32) / 255.0
        
        # 텍스처 업데이트
        if dpg.does_item_exist(current_mob_texture_tag):
            dpg.set_value(current_mob_texture_tag, data)
        
        # DPG Drawlist 오버레이 그리기 (cv2 대신)
        if dpg.does_item_exist("mob_drawlist"):
            # 기존 그림 삭제 (이미지 제외)
            dpg.delete_item("mob_drawlist", children_only=True)
            
            # 이미지 다시 그리기
            dpg.draw_image(current_mob_texture_tag, [0, 0], [mob_texture_width, mob_texture_height], parent="mob_drawlist")
            
            # 원본 크기 -> 텍스처 크기 변환 비율 계산
            orig_w = mob_selected_region['width']
            orig_h = mob_selected_region['height']
            scale_x = mob_texture_width / orig_w
            scale_y = mob_texture_height / orig_h
            
            with draw_data_lock:
                local_monsters = detected_monsters_for_draw.copy()
                local_ign = ign_box_for_draw
                local_attack = attack_box_for_draw
            
            # IGN 박스 그리기 (파란색 채움)
            if local_ign:
                x1, y1, x2, y2 = local_ign
                dpg.draw_rectangle(
                    [x1 * scale_x, y1 * scale_y], 
                    [x2 * scale_x, y2 * scale_y], 
                    color=[0, 0, 255, 255], 
                    fill=[0, 0, 255, 255],
                    parent="mob_drawlist"
                )
            
            # 공격 범위 박스 그리기 (파란색 테두리)
            if local_attack:
                x1, y1, x2, y2 = local_attack
                dpg.draw_rectangle(
                    [x1 * scale_x, y1 * scale_y], 
                    [x2 * scale_x, y2 * scale_y], 
                    color=[0, 0, 255, 255], 
                    thickness=3,
                    parent="mob_drawlist"
                )
            
            # 몬스터 점 그리기 (녹색)
            for mx, my in local_monsters:
                dpg.draw_circle(
                    [mx * scale_x, my * scale_y], 
                    radius=2, 
                    color=[0, 255, 0, 255], 
                    fill=[0, 255, 0, 255],
                    parent="mob_drawlist"
                )
            
        # 좌표 업데이트
        from normal_setting import minimap
        pos = minimap.get_player_position()
        if pos and dpg.does_item_exist("mob_xy_text"):
             dpg.set_value("mob_xy_text", f"X: {pos[0]:.1f} | Y: {pos[1]:.1f}")
            
    except Exception as e:
        print(f"Mob area update error: {e}")

def toggle_mob_window():
    """T키로 윈도우 토글"""
    global is_mob_window_open
    is_mob_window_open = not is_mob_window_open
    if dpg.does_item_exist("mob_window"):
        if is_mob_window_open:
            dpg.show_item("mob_window")
        else:
            dpg.hide_item("mob_window")

def hotkey_listener():
    """F5 키 감지하여 윈도우 토글"""
    VK_F5 = 0x76
    f5_pressed = False
    
    while True:
        try:
            state = ctypes.windll.user32.GetAsyncKeyState(VK_F5) & 0x8000
            if state and not f5_pressed:
                f5_pressed = True
                toggle_mob_window()
            elif not state:
                f5_pressed = False
            time.sleep(0.05)
        except:
            time.sleep(1)

# 핫키 리스너 시작
threading.Thread(target=hotkey_listener, daemon=True).start()

def render_training_area():
    """UI 렌더링"""
    dpg.add_button(label="몹감지구역", callback=select_mob_area, width=120, height=30)
